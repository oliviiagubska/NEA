import os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "login.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS teams(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  owner TEXT NOT NULL
)""")

cols = [r[1] for r in cur.execute("PRAGMA table_info(teams)")]
if "invite_code" not in cols:
    cur.execute("ALTER TABLE teams ADD COLUMN invite_code TEXT")

cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  username TEXT NOT NULL
)""")

con.commit()
print("OK ->", DB_PATH, "| columns:", [r[1] for r in con.execute("PRAGMA table_info(teams)")])
con.close()
