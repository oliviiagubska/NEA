import sqlite3
con = sqlite3.connect("login.db")
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, owner TEXT NOT NULL)")
try:
    cur.execute("ALTER TABLE teams ADD COLUMN invite_code TEXT UNIQUE")
except Exception:
    pass
cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    username TEXT NOT NULL
)""")
con.commit()
con.close()
print("ok")
