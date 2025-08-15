import sqlite3

con = sqlite3.connect("login.db")
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner TEXT NOT NULL
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id)
)""")

con.commit()
con.close()
print("tables ready")
