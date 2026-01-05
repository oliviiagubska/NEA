import sqlite3
import os

DB_NAME = "login.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

def create_tables():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
       username TEXT PRIMARY KEY,
       password TEXT NOT NULL,
       failed_attempts INTEGER NOT NULL DEFAULT 0,
       locked_until TEXT
   );
   """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner TEXT NOT NULL,
        invite_code TEXT UNIQUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        is_done INTEGER NOT NULL DEFAULT 0,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    con.commit()
    con.close()
    print("Database created at:", DB_PATH)

if __name__ == "__main__":
    create_tables()
