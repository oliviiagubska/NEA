import sqlite3

con = sqlite3.connect("login.db")
cur = con.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
''')

con.commit()
con.close()
print("users table created in login.db")
