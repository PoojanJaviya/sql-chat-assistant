import sqlite3
import os

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'hackathon.db')
SQL_SCRIPT_PATH = os.path.join(DATA_DIR, 'seed_data.sql')

def init_database():
    # Ensure data directory exists
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created directory: {DATA_DIR}")

    # Read SQL script
    try:
        with open(SQL_SCRIPT_PATH, 'r') as f:
            sql_script = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find seed data at {SQL_SCRIPT_PATH}")
        return

    # Connect to SQLite (creates file if missing)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Execute the script
        cursor.executescript(sql_script)
        conn.commit()
        conn.close()
        
        print(f"Success! Database initialized at: {DB_PATH}")
        print("Tables created and seed data inserted.")
        
    except Exception as e:
        print(f"Database initialization failed: {e}")

if __name__ == "__main__":
    init_database()