import sqlite3, os, sys
con = sqlite3.connect("login.db")
cur = con.cursor()
try:
    cur.execute("ALTER TABLE teams ADD COLUMN invite_code TEXT UNIQUE")
except Exception as e:
    pass
cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    username TEXT NOT NULL
)""")
con.commit()
con.close()
print("ok")
