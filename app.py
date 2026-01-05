from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import hashlib
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your-secret-key"

DB_PATH = os.path.join(os.path.dirname(__file__), "login.db")

def db():
    return sqlite3.connect(DB_PATH)

@app.route("/view_users")
def view_users():
    con = sqlite3.connect("login.db")
    cur = con.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    con.close()
    return str(rows)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]

        if len(u) < 3:
            return render_template("signup.html", error="Username must be at least 3 characters")

        con = db()
        cur = con.cursor()

        cur.execute("SELECT 1 FROM users WHERE username=?", (u,))
        if cur.fetchone():
            con.close()
            return render_template("signup.html", error="Username already exists")

        if len(p) < 6:
            con.close()
            return render_template("signup.html", error="Password must be at least 6 characters long")

        if not any(ch.isupper() for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one capital letter")

        if not any(ch.isdigit() for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one number")

        symbols = "!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~"
        if not any(ch in symbols for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one symbol")

        hp = hashlib.sha256(p.encode()).hexdigest()

        cur.execute(
            "INSERT INTO users(username, password, failed_attempts, locked_until) VALUES(?, ?, 0, NULL)",
            (u, hp)
        )

        con.commit()
        con.close()
        return redirect("/login")

    return render_template("signup.html", error=None)




from datetime import datetime, timedelta

LOCKOUT_ATTEMPTS = 3
LOCKOUT_MINUTES = 5

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        hp = hashlib.sha256(p.encode()).hexdigest()

        con = db()
        cur = con.cursor()

        cur.execute("""
            SELECT password, failed_attempts, locked_until
            FROM users
            WHERE username=?
        """, (u,))
        row = cur.fetchone()

        if not row:
            con.close()
            return render_template("login.html", error="Login failed")

        stored_hash, attempts, locked_until = row

        if locked_until:
            locked_time = datetime.fromisoformat(locked_until)
            if datetime.now() < locked_time:
                con.close()
                return render_template(
                    "login.html",
                    error=f"Account locked. Try again after {locked_time.strftime('%H:%M:%S')}."
                )
            else:
                cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?", (u,))
                con.commit()
                attempts = 0
                locked_until = None

        if hp == stored_hash:
            cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?", (u,))
            con.commit()
            con.close()

            session["username"] = u
            return redirect("/welcome")

        attempts += 1

        if attempts >= LOCKOUT_ATTEMPTS:
            lock_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
            cur.execute("""
                UPDATE users
                SET failed_attempts=?, locked_until=?
                WHERE username=?
            """, (attempts, lock_until.isoformat(), u))
            con.commit()
            con.close()
            return render_template("login.html", error="Too many failed attempts. Account locked for 5 minutes.")

        cur.execute("UPDATE users SET failed_attempts=? WHERE username=?", (attempts, u))
        con.commit()
        con.close()
        return render_template("login.html", error=f"Login failed ({attempts}/{LOCKOUT_ATTEMPTS})")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

def new_code():
    con = db()
    cur = con.cursor()


    cur.execute("SELECT invite_code FROM teams ORDER BY id DESC LIMIT 1")
    last = cur.fetchone()

    if last is None:
        new_number = 1
    else:
        new_number = int(last[0]) + 1

    code = f"{new_number:08d}"

    con.close()
    return code

@app.route("/welcome")
def welcome():
    if "username" not in session:
        return redirect("/login")

    return render_template(
        "welcome.html",
        username=session["username"]
    )

@app.route("/create_team", methods=["GET","POST"])
def create_team():
    if "username" not in session:
        return redirect("/login")

    if request.method == "POST":
        tname = request.form["team_name"].strip()
        code = new_code()

        con = db(); cur = con.cursor()
        cur.execute(
            "INSERT INTO teams(name, owner, invite_code) VALUES(?,?,?)",
            (tname, session["username"], code)
        )
        con.commit(); con.close()
        return redirect("/app")

    return render_template("create_team.html")

@app.route("/create_task", methods=["POST"])
def create_task():
    if "username" not in session:
        return redirect("/login")

    u = session["username"]
    project_id = int(request.form["project_id"])
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip()

    if not title:
        return redirect("/projects")

    con = db(); cur = con.cursor()

    cur.execute("""
        SELECT t.owner
        FROM projects p
        JOIN teams t ON p.team_id = t.id
        WHERE p.id=?
    """, (project_id,))
    row = cur.fetchone()

    if not row or row[0] != u:
        con.close()
        return ("Forbidden", 403)

    cur.execute("""
        INSERT INTO tasks(project_id, title, description, task_type, personal_owner)
        VALUES(?,?,?,?,NULL)
    """, (project_id, title, description, "team"))

    con.commit(); con.close()
    return redirect("/projects")

@app.route("/create_personal_task", methods=["POST"])
def create_personal_task():
    if "username" not in session:
        return redirect("/login")

    u = session["username"]
    project_id = int(request.form["project_id"])
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip()

    if not title:
        return redirect("/projects")

    con = db(); cur = con.cursor()

    cur.execute("""
        SELECT p.team_id
        FROM projects
        p WHERE p.id=?
    """, (project_id,))
    pr = cur.fetchone()
    if not pr:
        con.close()
        return redirect("/projects")
    team_id = pr[0]

    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    owner = cur.fetchone()[0]

    allowed = False
    if owner == u:
        allowed = True
    else:
        cur.execute("SELECT 1 FROM team_members WHERE team_id=? AND username=?", (team_id, u))
        if cur.fetchone():
            allowed = True

    if not allowed:
        con.close()
        return ("Forbidden", 403)

    cur.execute("""
        INSERT INTO tasks(project_id, title, description, task_type, personal_owner)
        VALUES(?,?,?,?,?)
    """, (project_id, title, description, "personal", u))

    con.commit(); con.close()
    return redirect("/projects")



@app.route("/join_team", methods=["GET","POST"])
def join_team():
    if "username" not in session: 
        return redirect("/login")

    if request.method == "POST":
        code = request.form["code"].strip()
        con = db(); cur = con.cursor()

        cur.execute("SELECT id, owner FROM teams WHERE invite_code=?", (code,))
        row = cur.fetchone()

        if not row:
            con.close()
            return render_template("join_team.html", error="Invalid code")

        team_id, owner = row


        if session["username"] == owner:
            role = "owner"

        else:
            role = "member"

            cur.execute(
                "SELECT 1 FROM team_members WHERE team_id=? AND username=?",
                (team_id, session["username"])
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO team_members(team_id, username) VALUES(?,?)",
                    (team_id, session["username"])
                )
                con.commit()

        con.close()

        session["last_join_role"] = role

        return redirect("/app")

    return render_template("join_team.html", error=None)


@app.route("/app")
def app_home():
    if "username" not in session: 
        return redirect("/login")

    now = datetime.now()
    greet = "Good morning" if now.hour < 12 else ("Good afternoon" if now.hour < 18 else "Good evening")
    date_str = now.strftime("%A, %d %B %Y")
    name = session["username"]
    initials = name[:2].upper()

    join_role = session.pop("last_join_role", None)

    con = db(); cur = con.cursor()

    cur.execute("SELECT id,name,invite_code,owner FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1", (name,))
    owned = cur.fetchone()

    if owned:
        team = {"id": owned[0], "name": owned[1], "code": owned[2], "owner": owned[3]}
        con.close()
        role = "owner"
        return render_template(
            "owner_home.html",
            username=name,
            initials=initials,
            date_today=date_str,
            greeting=greet,
            team=team,
            role=role,
            join_role=join_role
        )

    cur.execute("""
        SELECT t.id,t.name,t.invite_code,t.owner
        FROM teams t JOIN team_members m ON t.id=m.team_id
        WHERE m.username=? ORDER BY m.id DESC LIMIT 1
    """, (name,))
    joined = cur.fetchone()
    con.close()

    if not joined:
        return redirect("/welcome")

    team = {"id": joined[0], "name": joined[1], "code": joined[2], "owner": joined[3]}

    completed = 7
    total = 10
    done = round(100 * completed / total) if total else 0
    todo = max(0, 100 - done)

    role = "member"

    return render_template(
        "member_home.html",
        username=name,
        initials=initials,
        date_today=date_str,
        greeting=greet,
        done=done,
        todo=todo,
        team=team,
        role=role,
        join_role=join_role
    )


@app.route("/inbox", methods=["GET", "POST"])
def inbox():
    if "username" not in session:
        return redirect("/login")

    u = session["username"]
    con = db()
    cur = con.cursor()

    cur.execute("SELECT id FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1", (u,))
    row = cur.fetchone()
    if not row:
        cur.execute("""
            SELECT t.id
            FROM teams t JOIN team_members m ON t.id = m.team_id
            WHERE m.username=? ORDER BY m.id DESC LIMIT 1
        """, (u,))
        row = cur.fetchone()

    if not row:
        con.close()
        return render_template("inbox.html", members=[], messages=[], username=u, chat_with=None)

    team_id = row[0]

    chat_with = request.args.get("with")  

    if request.method == "POST":
        msg = request.form["message"].strip()
        recipient = request.form.get("recipient") or None  
        if msg:
            cur.execute(
                "INSERT INTO messages(team_id, sender, recipient, content) VALUES(?,?,?,?)",
                (team_id, u, recipient, msg)
            )
            con.commit()

    cur.execute("SELECT username FROM team_members WHERE team_id=?", (team_id,))
    members = [r[0] for r in cur.fetchall()]
    owner = con.execute("SELECT owner FROM teams WHERE id=?", (team_id,)).fetchone()[0]
    if owner not in members:
        members.insert(0, owner)

    members = [m for m in members if m != u]

    if chat_with:
        cur.execute("""
            SELECT sender, recipient, content
            FROM messages
            WHERE team_id = ?
              AND (
                   (sender=? AND recipient=?)
                OR (sender=? AND recipient=?)
              )
            ORDER BY id ASC
        """, (team_id, u, chat_with, chat_with, u))
    else:
        cur.execute("""
            SELECT sender, recipient, content
            FROM messages
            WHERE team_id = ? AND recipient IS NULL
            ORDER BY id ASC
        """, (team_id,))

    messages = cur.fetchall()
    con.close()

    return render_template(
        "inbox.html",
        members=members,
        messages=messages,
        username=u,
        chat_with=chat_with
    )


def _current_team_id(username):
    con = db(); cur = con.cursor()
    cur.execute("SELECT id FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1", (username,))
    r = cur.fetchone()
    if not r:
        cur.execute("""SELECT t.id
                       FROM teams t JOIN team_members m ON t.id=m.team_id
                       WHERE m.username=? ORDER BY m.id DESC LIMIT 1""", (username,))
        r = cur.fetchone()
    con.close()
    return r[0] if r else None

@app.route("/projects", methods=["GET"])
def projects():
    if "username" not in session:
        return redirect("/login")
    u = session["username"]
    team_id = _current_team_id(u)
    if not team_id:
        return "<h3>Join or create a team first.</h3>"
    con = db(); cur = con.cursor()
    cur.execute("SELECT username FROM team_members WHERE team_id=?", (team_id,))
    members = [r[0] for r in cur.fetchall()]
    owner = con.execute("SELECT owner FROM teams WHERE id=?", (team_id,)).fetchone()[0]
    if owner not in members:
        members.insert(0, owner)
    cur.execute("SELECT id,name,owner FROM projects WHERE team_id=? ORDER BY id DESC", (team_id,))
    prows = cur.fetchall()
    projects = []
    for pid, pname, powner in prows:
        ...
    con.close()
    return render_template("projects.html", members=members, projects=projects, username=u)


@app.route("/projects/create", methods=["POST"])
def create_project():
    if "username" not in session:
        return redirect("/login")
    name = request.form["name"].strip()
    if not name:
        return redirect("/projects")
    team_id = _current_team_id(session["username"])
    con = db(); cur = con.cursor()
    cur.execute("INSERT INTO projects(team_id,name,owner) VALUES(?,?,?)", (team_id, name, session["username"]))
    con.commit(); con.close()
    return redirect("/projects")

@app.route("/projects/<int:pid>/add_member", methods=["POST"])
def add_project_member(pid):
    if "username" not in session:
        return redirect("/login")
    user = request.form["username"].strip()
    if not user:
        return redirect("/projects")
    con = db(); cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO project_members(project_id,username) VALUES(?,?)", (pid, user))
    con.commit(); con.close()
    return redirect("/projects")

@app.route("/projects/assign", methods=["POST"])
def assign_member():
    if "username" not in session:
        return ("", 403)
    data = request.get_json(force=True)
    task_id = int(data.get("task_id"))
    username = data.get("username", "").strip()
    action = data.get("action", "add")
    con = db(); cur = con.cursor()
    if action == "add":
        cur.execute("INSERT OR IGNORE INTO task_assignees(task_id,username) VALUES(?,?)", (task_id, username))
    else:
        cur.execute("DELETE FROM task_assignees WHERE task_id=? AND username=?", (task_id, username))
    con.commit(); con.close()
    return {"ok": True}

@app.route("/members")
def members():
    if "username" not in session:
        return redirect("/login")

    u = session["username"]
    team_id = _current_team_id(u)
    if not team_id:
        return "<h3>Create or join a team first.</h3>"

    con = db(); cur = con.cursor()

    cur.execute("SELECT name, owner, invite_code FROM teams WHERE id=?", (team_id,))
    row = cur.fetchone()
    team = {"name": row[0], "owner": row[1], "code": row[2]}



    cur.execute("SELECT username FROM team_members WHERE team_id=? ORDER BY id", (team_id,))
    members = [r[0] for r in cur.fetchall()]


    if team["owner"] not in members:
        members.insert(0, team["owner"])

    con.close()

    return render_template(
        "members.html",
        username=u,
        team=team,
        members=members,
    )

@app.route("/notifications")
def notifications():
    if "username" not in session:
        return redirect("/login")
    u = session["username"]

    notifications = []

    return render_template("notifications.html",
                           username=u,
                           notifications=notifications)







if __name__ == "__main__":
    app.run(debug=True)