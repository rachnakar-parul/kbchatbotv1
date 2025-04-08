import pandas as pd
import sqlite3

# Load CSV file (Replace 'your_file.csv' with your actual CSV filename)
csv_file = "recipes2.csv"
df = pd.read_csv(csv_file)

# Connect to SQLite Database (Creates 'recipes.db' if it doesn’t exist)
conn = sqlite3.connect("recipes2.db")
cursor = conn.cursor()

# Rename your table (Use 'recipes' or any table name you want)
table_name = "recipes2"

# Convert CSV data into an SQLite table
df.to_sql(table_name, conn, if_exists="replace", index=False)

# Commit and close the connection
conn.commit()
conn.close()

print(f"✅ Successfully converted {csv_file} into {table_name} table in recipes.db!")