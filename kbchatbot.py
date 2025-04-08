from flask import Flask, request, render_template
from twilio.twiml.messaging_response import MessagingResponse
from flask_caching import Cache
import sqlite3
import os

# Force Flask to reload templates on change
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Store user progress based on their phone number
user_sessions = {}

def get_recipe_count(ingredient):
    conn = sqlite3.connect("recipes2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM recipes2 WHERE LOWER(`Key Ingredient`) LIKE LOWER(?)", ('%' + ingredient.strip() + '%',))
    count = cursor.fetchone()[0]
    conn.close()
    return count

@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.form.get("Body").strip().lower()
    sender_number = request.form.get("From")

    resp = MessagingResponse()
    reply = resp.message()

    if sender_number not in user_sessions or incoming_msg == "hi":
        user_sessions[sender_number] = {"step": "meal_selection"}
        reply.body("Welcome! What meal would you like to cook?\n1. Breakfast\n2. Dinner")
        return str(resp)

    session = user_sessions[sender_number]

    if session["step"] == "meal_selection":
        if incoming_msg == "1":
            session["meal_type"] = "Breakfast"
            session["step"] = "ingredient_selection"
            reply.body("Great! Select an ingredient:\n1. Poha\n2. Bread\n3. Besan\n4. Eggs\n5. Rice")
        elif incoming_msg == "2":
            session["meal_type"] = "Dinner"
            session["step"] = "ingredient_selection"
            reply.body("Great! Select an ingredient (Dinner options coming soon!)")
        else:
            reply.body("Invalid choice. Please type 1 for Breakfast or 2 for Dinner.")
        return str(resp)

    if session["step"] == "ingredient_selection":
        breakfast_ingredients = {
            "1": "Poha",
            "2": "Bread",
            "3": "Besan",
            "4": "Eggs",
            "5": "Rice"
        }

        if incoming_msg in breakfast_ingredients:
            session["ingredient"] = breakfast_ingredients[incoming_msg]
            session["step"] = "show_results"
            dynamic_link = f"https://7b1e-2401-4900-1c5c-b72a-d151-6e38-f017-acde.ngrok-free.app/recipes/{session['ingredient']}"
            reply.body(f"Found recipes for {session['ingredient']}! Click here to view: {dynamic_link}")
        else:
            reply.body("Invalid choice. Please select an ingredient from the list.")
        
        return str(resp)

def get_recipes(ingredient, sort_by="Cooking_Time", order="asc"):
    conn = sqlite3.connect("recipes2.db")
    cursor = conn.cursor()

    # ✅ Validate sorting parameter
    valid_sort_columns = ["Cooking_Time", "Spice Level"]
    if sort_by not in valid_sort_columns:
        sort_by = "Cooking_Time"

    # ✅ Convert spice levels to numeric values for sorting
    if sort_by == "Spice Level":
        sort_by = """
        CASE `Spice Level`
            WHEN 'Low' THEN 1
            WHEN 'Medium' THEN 2
            WHEN 'High' THEN 3
            ELSE 0
        END
        """

    # ✅ Ensure sorting order is valid (ASC/DESC)
    order = "ASC" if order.lower() == "asc" else "DESC"

    # ✅ Fetch sorted recipes
    query = f"""
        SELECT `Dish Name`, `Image`, `Meal Type`, `State`, `Prep_time`, `Cooking_Time`, `Spice Level`
        FROM recipes2
        WHERE LOWER(`Key Ingredient`) LIKE LOWER(?)
        ORDER BY {sort_by} {order}
    """
    cursor.execute(query, ('%' + ingredient.strip() + '%',))
    recipes = cursor.fetchall()
    conn.close()
    return recipes

# Route to Display Recipes Page with Sorting & Caching
@app.route("/recipes/<ingredient>")
@cache.cached(timeout=120, query_string=True)  # Cache for 2 minutes, respect sorting parameters
def show_recipes(ingredient):
    # Get sorting parameters from user
    sort_by = request.args.get("sort_by", "Cooking_Time")  # Default sorting by cooking time
    order = request.args.get("order", "asc")

    recipes = get_recipes(ingredient, sort_by, order)
    recipe_count = len(recipes)

    processed_recipes = []
    for recipe in recipes:
        dish_name, image, meal_type, state, prep_time, cooking_time, spice_level = recipe

        try:
            prep_time = int(prep_time) if str(prep_time).isdigit() else 0
            cooking_time = int(cooking_time) if str(cooking_time).isdigit() else 0
        except ValueError:
            prep_time, cooking_time = 0, 0

        total_time = prep_time + cooking_time

        if not image or image.strip() == "":
            image = "https://via.placeholder.com/270x150?text=No+Image"

        spice_icons = {
            "Low": "🌶️",
            "Medium": "🌶️🌶️",
            "High": "🌶️🌶️🌶️"
        }
        spice_display = spice_icons.get(spice_level, "")

        processed_recipes.append((dish_name, image, meal_type, state, total_time, spice_display))

    return render_template("recipe.html", ingredient=ingredient, recipes=processed_recipes, recipe_count=recipe_count, sort_by=sort_by, order=order)

# Route to Show Individual Recipe Details
@app.route("/recipe/<recipe_name>")
def show_recipe_details(recipe_name):
    conn = sqlite3.connect("recipes2.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT `Dish Name`, `Prep_time`, `Cooking_Time`, `State`, `Spice Level`, `Ingredient List`, `Instructions`, `Video`, `Image`
        FROM recipes2 WHERE `Dish Name` = ?
    """, (recipe_name,))
    
    recipe = cursor.fetchone()
    conn.close()

    if not recipe:
        return "<h2>Recipe not found.</h2>"

    dish_name = recipe[0]
    prep_time = recipe[1] if recipe[1] else 0
    cooking_time = recipe[2] if recipe[2] else 0
    state = recipe[3] if recipe[3] else "Unknown"
    spice_level = recipe[4] if recipe[4] else "Low"

    ingredient_list = ingredient_list = [line.strip() for line in recipe[5].split('\n') if line.strip()]

    instructions = [step.strip() for step in recipe[6].split("\n") if step.strip()]


    video_link = recipe[7] if recipe[7] else "#"
    image_link = recipe[8] if recipe[8] else "https://via.placeholder.com/400"

    return render_template("recipe_details.html",
                           dish_name=dish_name,
                           prep_time=int(prep_time),
                           cooking_time=int(cooking_time),
                           state=state,
                           spice_level=spice_level,
                           ingredient_list=ingredient_list,
                           instructions=instructions,
                           video_link=video_link,
                           image_link=image_link)

@app.route("/test", methods=["GET"])
def test():
    test_number = "+911234567890"
    test_message = request.args.get("msg", "").strip().lower()

    if not test_message:
        return "❌ Please provide a message using ?msg=yourtext"

    print(f"✅ Simulated message: {test_message} from {test_number}")

    request.form = {"Body": test_message, "From": test_number}
    return bot()

if __name__ == "__main__":
    app.run(debug=True)
