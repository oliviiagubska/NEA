from flask import Flask, render_template, request, redirect, session
import os, sqlite3, hashlib, random
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "login.db")

def db():
    return sqlite3.connect(DB_PATH)

def ensure_schema():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS teams(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner TEXT NOT NULL,
        invite_code TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS team_members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        username TEXT NOT NULL
    )""")
    cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_team_members_unique
                   ON team_members(team_id, username)""")
    con.commit(); con.close()

ensure_schema()

app = Flask(__name__)
app.secret_key = "your-secret-key"

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        hp = hashlib.sha256(p.encode()).hexdigest()
        con = db(); cur = con.cursor()
        cur.execute("SELECT 1 FROM users WHERE username=?", (u,))
        if cur.fetchone():
            con.close()
            return render_template("signup.html", error="Username already exists")
        cur.execute("INSERT INTO users(username,password) VALUES(?,?)", (u,hp))
        con.commit(); con.close()
        return redirect("/login")
    return render_template("signup.html", error=None)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        hp = hashlib.sha256(p.encode()).hexdigest()
        con = db(); cur = con.cursor()
        cur.execute("SELECT 1 FROM users WHERE username=? AND password=?", (u,hp))
        ok = cur.fetchone(); con.close()
        if ok:
            session["username"] = u
            return redirect("/welcome")
        return render_template("login.html", error="Login failed")
    return render_template("login.html", error=None)

@app.route("/welcome")
def welcome():
    if "username" not in session: return redirect("/login")
    return render_template("welcome.html", username=session["username"])

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

def new_code():
    con = db(); cur = con.cursor()
    while True:
        c = "".join(random.choice("0123456789") for _ in range(8))
        cur.execute("SELECT 1 FROM teams WHERE invite_code=?", (c,))
        if not cur.fetchone():
            con.close()
            return c

@app.route("/create_team", methods=["GET","POST"])
def create_team():
    if "username" not in session: return redirect("/login")
    if request.method == "POST":
        tname = request.form["team_name"].strip()
        code = new_code()
        con = db(); cur = con.cursor()
        cur.execute("INSERT INTO teams(name, owner, invite_code) VALUES(?,?,?)",
                    (tname, session["username"], code))
        con.commit(); con.close()
        return redirect("/app")
    return render_template("create_team.html")

@app.route("/join_team", methods=["GET","POST"])
def join_team():
    if "username" not in session: return redirect("/login")
    if request.method == "POST":
        code = request.form["code"].strip()
        con = sqlite3.connect(DB_PATH); cur = con.cursor()
        cur.execute("SELECT id FROM teams WHERE invite_code=?", (code,))
        row = cur.fetchone()
        if not row:
            con.close()
            return render_template("join_team.html", error="Invalid code")
        team_id = row[0]
        cur.execute("SELECT 1 FROM team_members WHERE team_id=? AND username=?",
                    (team_id, session["username"]))
        if not cur.fetchone():
            cur.execute("INSERT INTO team_members(team_id, username) VALUES(?,?)",
                        (team_id, session["username"]))
            con.commit()
        con.close()
        return redirect("/app")
    return render_template("join_team.html", error=None)


@app.route("/app")
def app_home():
    if "username" not in session: return redirect("/login")
    now = datetime.now()
    greet = "Good morning" if now.hour < 12 else ("Good afternoon" if now.hour < 18 else "Good evening")
    date_str = now.strftime("%A, %d %B %Y")
    name = session["username"]
    initials = name[:2].upper()
    done, todo = 68, 32
    con = db(); cur = con.cursor()
    cur.execute(
    "SELECT id,name,invite_code FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1",
    (name,)
    )
    t = cur.fetchone()
    if not t:
        cur.execute(
            """SELECT t.id,t.name,t.invite_code
               FROM teams t JOIN team_members m ON t.id=m.team_id
               WHERE m.username=? ORDER BY m.id DESC LIMIT 1""",
            (name,)
        )
        t = cur.fetchone()

    con.close()
    team = {"id": t[0], "name": t[1], "code": t[2]} if t else None
    return render_template("app_home.html",
                           username=name, initials=initials,
                           date_today=date_str, greeting=greet,
                           done=done, todo=todo, team=team)

if __name__ == "__main__":
    app.run(debug=True)
