from flask import Flask, render_template, request, redirect, session, abort, jsonify
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta, date

#create flask app
app = Flask(__name__)
app.secret_key = "your-secret-key"

#path to the database file
DB_PATH = os.path.join(os.path.dirname(__file__), "login.db")

#connect to sqlite database
def db():
    return sqlite3.connect(DB_PATH)

#add a notification to the database
def add_notification(team_id, username, text):
    #save notifications in one place so routes stay clean
    with db() as con:
        con.execute("""
            INSERT INTO notifications(team_id, username, text, created_at, seen)
            VALUES(?, ?, ?, ?, 0)
        """, (team_id, username, text, datetime.now().isoformat()))

#debug route to view all users
@app.route("/view_users")
def view_users():
    if "username" not in session:
        abort(403)

    with db() as con:
        cur = con.cursor()
        cur.execute("SELECT username FROM users ORDER BY username")
        rows = cur.fetchall()

    return "<br>".join([r[0] for r in rows])

#home page
@app.route("/")
def home():
    return render_template("home.html")

#signup page
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        #get form data
        u = request.form["username"].strip()
        p = request.form["password"]

        #check username length
        if len(u) < 3:
            return render_template("signup.html", error="Username must be at least 3 characters")

        con = db()
        cur = con.cursor()

        #check if username already exists
        cur.execute("SELECT 1 FROM users WHERE username=?", (u,))
        if cur.fetchone():
            con.close()
            return render_template("signup.html", error="Username already exists")

        #password length check
        if len(p) < 6:
            con.close()
            return render_template("signup.html", error="Password must be at least 6 characters long")

        #password must contain a capital letter
        if not any(ch.isupper() for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one capital letter")

        #password must contain a number
        if not any(ch.isdigit() for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one number")

        #password must contain a symbol
        symbols = "!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~"
        if not any(ch in symbols for ch in p):
            con.close()
            return render_template("signup.html", error="Password must contain at least one symbol")

        #hash the password 
        hp = hashlib.sha256(p.encode()).hexdigest()

        #insert new user into database
        cur.execute(
            "INSERT INTO users(username, password, failed_attempts, locked_until) VALUES(?, ?, 0, NULL)",
            (u, hp)
        )

        con.commit()
        con.close()

        #redirect to login page
        return redirect("/login")

    #load signup page
    return render_template("signup.html", error=None)

#maximum number of failed login attempts
LOCKOUT_ATTEMPTS = 3

#lockout time in minutes
LOCKOUT_MINUTES = 5

#login route
@app.route("/login", methods=["GET","POST"])
def login():

    #handle form submission
    if request.method == "POST":

        #get login details from form
        u = request.form["username"].strip()
        p = request.form["password"]

        #hash entered password
        hp = hashlib.sha256(p.encode()).hexdigest()

        con = db()
        cur = con.cursor()

        #get stored password and lock data
        cur.execute("""
            SELECT password, failed_attempts, locked_until
            FROM users
            WHERE username=?
        """, (u,))
        row = cur.fetchone()

        #if user does not exist
        if not row:
            con.close()
            return render_template("login.html", error="Login failed")

        stored_hash, attempts, locked_until = row

        #check if account is locked
        if locked_until:
            locked_time = datetime.fromisoformat(locked_until)

            #still locked
            if datetime.now() < locked_time:
                con.close()
                return render_template(
                    "login.html",
                    error=f"Account locked. Try again after {locked_time.strftime('%H:%M:%S')}."
                )

            #lock expired so reset values
            else:
                cur.execute(
                    "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?",
                    (u,)
                )
                con.commit()
                attempts = 0

        #password correct
        if hp == stored_hash:
            cur.execute(
                "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?",
                (u,)
            )
            con.commit()
            con.close()

            #store user session
            session["username"] = u
            return redirect("/welcome")

        #password incorrect
        attempts += 1

        #lock account if too many attempts
        if attempts >= LOCKOUT_ATTEMPTS:
            lock_until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
            cur.execute("""
                UPDATE users
                SET failed_attempts=?, locked_until=?
                WHERE username=?
            """, (attempts, lock_until.isoformat(), u))
            con.commit()
            con.close()
            return render_template(
                "login.html",
                error="Too many failed attempts. Account locked for 5 minutes."
            )

        #update failed attempts counter
        cur.execute("UPDATE users SET failed_attempts=? WHERE username=?", (attempts, u))
        con.commit()
        con.close()

        return render_template(
            "login.html",
            error=f"Login failed ({attempts}/{LOCKOUT_ATTEMPTS})"
        )

    #load login page
    return render_template("login.html", error=None)


#logout route  
@app.route("/logout")
def logout():
    #remove username from session
    session.pop("username", None)
    #redirect to home page
    return redirect("/")

#generate a new 8 digit invite code in order
def new_code():
    with db() as con:
        cur = con.cursor()

        # get highest numeric invite code
        cur.execute("""
            SELECT invite_code
            FROM teams
            WHERE invite_code GLOB '[0-9]*'
            ORDER BY CAST(invite_code AS INTEGER) DESC
            LIMIT 1
        """)
        row = cur.fetchone()

        if not row:
            new_number = 0
        else:
            new_number = int(row[0]) + 1

        return f"{new_number:08d}"


#welcome page after login
@app.route("/welcome")
def welcome():
    #check if user is logged in
    if "username" not in session:
        return redirect("/login")

    #load welcome page
    return render_template(
        "welcome.html",
        username=session["username"]
    )

@app.route("/create_team", methods=["GET", "POST"])
def create_team():

    #check login
    if "username" not in session:
        return redirect("/login")

    #handle form submission
    if request.method == "POST":

        #get team name from form
        tname = request.form["team_name"].strip()

        #basic validation
        if not tname:
            return render_template("create_team.html", error="Team name is required")

        #generate invite code
        code = new_code()

        #insert team into database
        con = db()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO teams(name, owner, invite_code) VALUES(?,?,?)",
            (tname, session["username"], code)
        )

        #get the id of the newly created team
        team_id = cur.lastrowid

        con.commit()
        con.close()

        #set this team as the active team
        session["active_team_id"] = team_id

        #go to dashboard
        return redirect("/app")

    #load create team page
    return render_template("create_team.html", error=None)


#create a team task
@app.route("/create_task", methods=["POST"])
def create_task():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get data
    project_id = int(request.form["project_id"])
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip()
    date_due = request.form.get("date_due", "").strip()

    #prevent empty task titles
    if not title:
        return redirect("/projects")

    #task title must be at least 3 characters
    if len(title) < 3:
        return ("Bad Request: task title must be at least 3 characters", 400)

    #task title max length
    if len(title) > 50:
        return ("Bad Request: task title must be max 50 characters", 400)

    #deadline must exist
    if not date_due:
        return ("Bad Request: deadline is required", 400)

    con = db()
    cur = con.cursor()

    #check project owner and team id
    cur.execute("""
        SELECT t.owner, p.team_id
        FROM projects p
        JOIN teams t ON p.team_id = t.id
        WHERE p.id=?
    """, (project_id,))
    row = cur.fetchone()

    #if project not found
    if not row:
        con.close()
        return redirect("/projects")

    owner, team_id = row

    #only owner can create tasks
    if owner != u:
        con.close()
        return ("Forbidden", 403)

    try:
        due_date = date.fromisoformat(date_due)  # expects YYYY-MM-DD from <input type="date">
    except ValueError:
        con.close()
        return ("Bad Request: invalid deadline format", 400)

    if due_date < date.today():
        con.close()
        return ("Bad Request: deadline cannot be in the past", 400)

    #insert task into database
    cur.execute("""
        INSERT INTO tasks (
            project_id,
            title,
            description,
            task_type,
            personal_owner,
            date_assigned,
            date_due,
            status
        )
        VALUES (?, ?, ?, 'team', NULL, ?, ?, 0)
    """, (
        project_id,
        title,
        description,
        datetime.now().isoformat(),
        date_due
    ))
    task_id = cur.lastrowid

    #get selected assignees
    assignees = request.form.getlist("assignees")

    #assign users to task
    for m in assignees:
        cur.execute("""
            INSERT INTO task_assignees (task_id, username, completed)
            VALUES (?, ?, 0)
        """, (task_id, m))

    con.commit()
    con.close()

    #send notification to assignees
    for m in assignees:
        if m != u:
            add_notification(team_id, m, f"{u} assigned you a task: {title}")

    return redirect("/projects")



#mark a task as done by a user
@app.route("/tasks/<int:task_id>/done", methods=["POST"])
def mark_task_done(task_id):

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    con = db()
    cur = con.cursor()

    #mark this users part of the task as completed
    cur.execute("""
        UPDATE task_assignees
        SET completed=1
        WHERE task_id=? AND username=?
    """, (task_id, u))

    #check if all assignees have completed the task
    cur.execute("""
        SELECT COUNT(*) FROM task_assignees
        WHERE task_id=? AND completed=0
    """, (task_id,))

    #if no incomplete assignees remain mark task as done
    if cur.fetchone()[0] == 0:
        cur.execute("""
            UPDATE tasks SET status=1 WHERE id=?
        """, (task_id,))

    con.commit()
    con.close()

    #return to projects page
    return redirect("/projects")


#create a personal task
@app.route("/create_personal_task", methods=["POST"])
def create_personal_task():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get form data
    project_id = int(request.form["project_id"])
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip()

    #prevent empty task titles
    if not title:
        return redirect("/projects")

    con = db()
    cur = con.cursor()

    #get team linked to this project
    cur.execute("""
        SELECT team_id
        FROM projects
        WHERE id=?
    """, (project_id,))
    pr = cur.fetchone()

    #if project does not exist
    if not pr:
        con.close()
        return redirect("/projects")

    team_id = pr[0]

    #get team owner
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    owner = cur.fetchone()[0]

    #check permission to create personal task
    allowed = False

    #owner can always create tasks
    if owner == u:
        allowed = True

    #members can create tasks for themselves
    else:
        cur.execute(
            "SELECT 1 FROM team_members WHERE team_id=? AND username=?",
            (team_id, u)
        )
        if cur.fetchone():
            allowed = True

    #block access if user is not allowed
    if not allowed:
        con.close()
        return ("Forbidden", 403)

    #insert personal task into database
    cur.execute("""
        INSERT INTO tasks(project_id,title,description,task_type,personal_owner,status)
        VALUES(?,?,?,?,?,0)
    """, (project_id, title, description, "personal", u))

    con.commit()
    con.close()

    #return to projects page
    return redirect("/projects")

#join a team using invite code
@app.route("/join_team", methods=["GET", "POST"])
def join_team():

    #check login
    if "username" not in session:
        return redirect("/login")

    if request.method == "POST":

        code = request.form["code"].strip()

        #basic validation
        if not code:
            return render_template("join_team.html", error="Code is required")

        con = db()
        cur = con.cursor()

        #find team with this invite code
        cur.execute("SELECT id, owner FROM teams WHERE invite_code=?", (code,))
        row = cur.fetchone()

        #if code is invalid
        if not row:
            con.close()
            return render_template("join_team.html", error="Invalid code")

        team_id, owner = row

        #owner joining their own team
        if session["username"] == owner:
            role = "owner"

        #member joining someone else's team
        else:
            role = "member"

            #check if already a member
            cur.execute(
                "SELECT 1 FROM team_members WHERE team_id=? AND username=?",
                (team_id, session["username"])
            )

            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO team_members(team_id, username) VALUES(?, ?)",
                    (team_id, session["username"])
                )
                con.commit()

        con.close()

        #set active team so /app shows the correct one
        session["active_team_id"] = team_id
        session["last_join_role"] = role

        return redirect("/app")

    return render_template("join_team.html", error=None)



@app.route("/app")
def app_home():

    #check login
    if "username" not in session:
        return redirect("/login")

    name = session["username"]

    #date + greeting
    now = datetime.now()
    greet = "Good morning" if now.hour < 12 else (
        "Good afternoon" if now.hour < 18 else "Good evening"
    )
    date_str = now.strftime("%A, %d %B %Y")

    initials = name[:2].upper()

    #role banner after joining a team
    join_role = session.pop("last_join_role", None)

    con = db()
    cur = con.cursor()

    #get currently active team
    team_id = _current_team_id(name)
    if not team_id:
        con.close()
        return redirect("/welcome")

    #get team details
    cur.execute(
        "SELECT id, name, invite_code, owner FROM teams WHERE id=?",
        (team_id,)
    )
    row = cur.fetchone()

    if not row:
        con.close()
        return redirect("/welcome")

    team = {
        "id": row[0],
        "name": row[1],
        "code": row[2],
        "owner": row[3]
    }


    #decide role
    role = "owner" if team["owner"] == name else "member"

    if role == "owner":

        #count all tasks in team
        cur.execute("""
            SELECT COUNT(*)
            FROM tasks tk
            JOIN projects p ON tk.project_id = p.id
            WHERE p.team_id=?
        """, (team_id,))
        total_tasks = cur.fetchone()[0]

        #count completed tasks
        cur.execute("""
            SELECT COUNT(*)
            FROM tasks tk
            JOIN projects p ON tk.project_id = p.id
            WHERE p.team_id=? AND tk.status=1
        """, (team_id,))
        done_tasks = cur.fetchone()[0]

        todo_tasks = total_tasks - done_tasks
        progress_percent = round((done_tasks / total_tasks) * 100) if total_tasks else 0

        con.close()

        return render_template(
            "owner_home.html",
            username=name,
            initials=initials,
            greeting=greet,
            date_today=date_str,
            team=team,
            role=role,
            join_role=join_role,
            total_tasks=total_tasks,
            done_tasks=done_tasks,
            todo_tasks=todo_tasks,
            progress_percent=progress_percent
        )

    #count tasks assigned to this member
    cur.execute("""
        SELECT COUNT(*)
        FROM task_assignees ta
        JOIN tasks tk ON ta.task_id = tk.id
        JOIN projects p ON tk.project_id = p.id
        WHERE p.team_id=? AND ta.username=?
    """, (team_id, name))
    total_tasks = cur.fetchone()[0]

    #count completed tasks by this member
    cur.execute("""
        SELECT COUNT(*)
        FROM task_assignees ta
        JOIN tasks tk ON ta.task_id = tk.id
        JOIN projects p ON tk.project_id = p.id
        WHERE p.team_id=? AND ta.username=? AND ta.completed=1
    """, (team_id, name))
    done_tasks = cur.fetchone()[0]

    todo_tasks = total_tasks - done_tasks
    progress_percent = round((done_tasks / total_tasks) * 100) if total_tasks else 0

    con.close()

    return render_template(
        "member_home.html",
        username=name,
        initials=initials,
        greeting=greet,
        date_today=date_str,
        team=team,
        role=role,
        join_role=join_role,
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        todo_tasks=todo_tasks,
        progress_percent=progress_percent
    )


#inbox page (team chat + private chat)
@app.route("/inbox", methods=["GET", "POST"])
def inbox():

    #check login
    if "username" not in session:
        return redirect("/login")

    #current user
    u = session["username"]

    con = db()
    cur = con.cursor()

    #check if user owns a team
    cur.execute(
        "SELECT id FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1",
        (u,)
    )
    row = cur.fetchone()

    #if not owner check if user is a member
    if not row:
        cur.execute("""
            SELECT t.id
            FROM teams t
            JOIN team_members m ON t.id = m.team_id
            WHERE m.username=?
            ORDER BY m.id DESC
            LIMIT 1
        """, (u,))
        row = cur.fetchone()

    #if user is not in a team show empty inbox
    if not row:
        con.close()
        return render_template(
            "inbox.html",
            members=[],
            messages=[],
            username=u,
            chat_with=None
        )

    #team id for this user
    team_id = row[0]

    #get private chat user from url ( ?with=username )
    chat_with = request.args.get("with")

    #sending a message
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        recipient = request.form.get("recipient") or None

        #only insert if message is not empty
        if msg:
            cur.execute(
                """
                INSERT INTO messages (team_id, sender, recipient, content)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, u, recipient, msg)
            )
            con.commit()

    #get team members list
    cur.execute(
        "SELECT username FROM team_members WHERE team_id=?",
        (team_id,)
    )
    members = [r[0] for r in cur.fetchall()]

    #make sure team owner is included in list
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    owner = cur.fetchone()[0]
    if owner not in members:
        members.insert(0, owner)

    #remove current user from list
    members = [m for m in members if m != u]

    #load messages depending on chat type
    if chat_with:
        #private chat messages (only between two users)
        cur.execute("""
            SELECT sender, recipient, content
            FROM messages
            WHERE team_id=?
              AND (
                (sender=? AND recipient=?)
                OR
                (sender=? AND recipient=?)
              )
            ORDER BY id ASC
        """, (team_id, u, chat_with, chat_with, u))
    else:
        #team chat messages (recipient is null)
        cur.execute("""
            SELECT sender, recipient, content
            FROM messages
            WHERE team_id=? AND recipient IS NULL
            ORDER BY id ASC
        """, (team_id,))

    messages = cur.fetchall()
    con.close()

    #load inbox page
    return render_template(
        "inbox.html",
        members=members,
        messages=messages,
        username=u,
        chat_with=chat_with
    )

#helper function to check if user is team owner
def _is_team_owner(username, team_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0] == username)

def _current_team_id(username):
    #if user has an active team selected use it
    active = session.get("active_team_id")
    if active:
        con = db()
        cur = con.cursor()

        #owner
        cur.execute("SELECT 1 FROM teams WHERE id=? AND owner=?", (active, username))
        if cur.fetchone():
            con.close()
            return active

        #member
        cur.execute("SELECT 1 FROM team_members WHERE team_id=? AND username=?", (active, username))
        if cur.fetchone():
            con.close()
            return active

        con.close()

    #latest owned team
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT id FROM teams WHERE owner=? ORDER BY id DESC LIMIT 1",
        (username,)
    )
    r = cur.fetchone()

    #latest joined team
    if not r:
        cur.execute("""
            SELECT t.id
            FROM teams t JOIN team_members m ON t.id=m.team_id
            WHERE m.username=? ORDER BY m.id DESC LIMIT 1
        """, (username,))
        r = cur.fetchone()

    con.close()
    return r[0] if r else None


#create a new project (owner only)
@app.route("/projects/create", methods=["POST"])
def create_project():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get project details from form
    name = request.form["name"].strip()

    #limit project name length
    if len(name) > 50:
        return redirect("/projects")
    description = request.form.get("description", "").strip()

    #prevent empty name
    if not name:
        return redirect("/projects")

    #get team id
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    con = db()
    cur = con.cursor()

    #only the team owner can create projects
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    owner = cur.fetchone()[0]
    if owner != u:
        con.close()
        return ("Forbidden", 403)

    #insert project into database
    cur.execute(
        "INSERT INTO projects(team_id, name, description, owner) VALUES(?, ?, ?, ?)",
        (team_id, name, description, u)
    )
    con.commit()

    #get all team members to notify
    cur.execute("SELECT username FROM team_members WHERE team_id=?", (team_id,))
    members = [r[0] for r in cur.fetchall()]

    con.close()

    #send notifications to members
    for m in members:
        add_notification(team_id, m, f"{u} created a new project: {name}")

    return redirect("/projects")

#delete project (owner only)
@app.route("/projects/<int:pid>/delete", methods=["POST"])
def delete_project(pid):

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get current team id
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    con = db()
    cur = con.cursor()

    #check project team id and find the owner of that team
    cur.execute("""
        SELECT p.team_id, t.owner
        FROM projects p
        JOIN teams t ON p.team_id = t.id
        WHERE p.id=?
    """, (pid,))
    row = cur.fetchone()

    #if project not found
    if not row:
        con.close()
        return redirect("/projects")

    project_team_id, team_owner = row

    #only team owner can delete the project
    if project_team_id != team_id or team_owner != u:
        con.close()
        return ("Forbidden", 403)

    #delete task assignees for tasks in this project
    cur.execute("""
        DELETE FROM task_assignees
        WHERE task_id IN (
            SELECT id FROM tasks WHERE project_id=?
        )
    """, (pid,))

    #delete tasks in this project
    cur.execute("DELETE FROM tasks WHERE project_id=?", (pid,))

    #delete links from project_members table
    cur.execute("DELETE FROM project_members WHERE project_id=?", (pid,))

    #delete project
    cur.execute("DELETE FROM projects WHERE id=?", (pid,))

    con.commit()
    con.close()

    return redirect("/projects")


#delete a task (owner only)
@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get current team id for user
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    con = db()
    cur = con.cursor()

    #find which team this task belongs to and who the team owner is
    cur.execute("""
        SELECT p.team_id, t.owner
        FROM tasks tk
        JOIN projects p ON tk.project_id = p.id
        JOIN teams t ON p.team_id = t.id
        WHERE tk.id=?
    """, (task_id,))
    row = cur.fetchone()

    #if task not found
    if not row:
        con.close()
        return redirect("/projects")

    task_team_id, team_owner = row

    #only the team owner can delete tasks
    if task_team_id != team_id or team_owner != u:
        con.close()
        return ("Forbidden", 403)

    #delete assignee links first
    cur.execute("DELETE FROM task_assignees WHERE task_id=?", (task_id,))

    #delete the task
    cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    con.commit()
    con.close()

    #return to projects page
    return redirect("/projects")


#add a member to a project (owner only and user must be in the team)
@app.route("/projects/<int:pid>/add_member", methods=["POST"])
def add_project_member(pid):

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]
    user = request.form.get("username", "").strip()

    #prevent empty input
    if not user:
        return redirect("/projects")

    #get current team id
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    con = db()
    cur = con.cursor()

    #only the team owner can add project members
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    row = cur.fetchone()
    if not row or row[0] != u:
        con.close()
        return ("Forbidden", 403)

    #make sure this project belongs to the current team
    cur.execute("SELECT team_id FROM projects WHERE id=?", (pid,))
    pr = cur.fetchone()
    if not pr or pr[0] != team_id:
        con.close()
        return ("Not Found", 404)

    #only allow adding users that are actually in this team (or the owner)
    if user != u:
        cur.execute("SELECT 1 FROM team_members WHERE team_id=? AND username=?", (team_id, user))
        if not cur.fetchone():
            con.close()
            return ("Bad Request: user is not in this team", 400)

    #add user to project members (ignore if already exists)
    cur.execute(
        "INSERT OR IGNORE INTO project_members(project_id,username) VALUES(?,?)",
        (pid, user)
    )

    con.commit()
    con.close()

    return redirect("/projects")


#assign or unassign users to tasks (owner only with js)
@app.route("/projects/assign", methods=["POST"])
def assign_member():

    #check login
    if "username" not in session:
        return ("", 403)

    u = session["username"]

    #get team id for user
    team_id = _current_team_id(u)
    if not team_id:
        return ("", 403)

    #get json data from request
    data = request.get_json(force=True) or {}

    #read values from json
    task_id = int(data.get("task_id", 0))
    username = (data.get("username") or "").strip()
    action = data.get("action", "add")

    if not task_id or not username:
        return ("", 400)

    con = db()
    cur = con.cursor()

    #only team owner can assign people
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    row = cur.fetchone()
    if not row or row[0] != u:
        con.close()
        return ("", 403)

    #ensure the task belongs to the current team
    cur.execute("""
        SELECT p.team_id
        FROM tasks tk
        JOIN projects p ON tk.project_id = p.id
        WHERE tk.id=?
    """, (task_id,))
    r = cur.fetchone()
    if not r or r[0] != team_id:
        con.close()
        return ("", 404)

    #assign user to task
    if action == "add":
        cur.execute(
            "INSERT OR IGNORE INTO task_assignees(task_id,username,completed) VALUES(?,?,0)",
            (task_id, username)
        )

    #remove user from task
    else:
        cur.execute(
            "DELETE FROM task_assignees WHERE task_id=? AND username=?",
            (task_id, username)
        )

    con.commit()
    con.close()

    #return json response for fetch()
    return jsonify({"ok": True})


#members page (shows owner + team members)
@app.route("/members")
def members():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get team id for user
    team_id = _current_team_id(u)
    if not team_id:
        return "<h3>Create or join a team first.</h3>"

    con = db()
    cur = con.cursor()

    #get team name and owner
    cur.execute("SELECT name, owner FROM teams WHERE id=?", (team_id,))
    name, owner = cur.fetchone()

    #get members list
    cur.execute("SELECT username FROM team_members WHERE team_id=?", (team_id,))
    members = [r[0] for r in cur.fetchall()]

    #make sure owner is included
    if owner not in members:
        members.insert(0, owner)

    con.close()

    #load members page
    return render_template(
        "members.html",
        team_name=name,
        owner=owner,
        members=members
    )


#notifications page (shows user updates)
@app.route("/notifications")
def notifications():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get current team id
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    con = db()
    cur = con.cursor()

    #get latest notifications for this user
    cur.execute("""
        SELECT text, created_at
        FROM notifications
        WHERE team_id=? AND username=?
        ORDER BY id DESC
        LIMIT 50
    """, (team_id, u))
    rows = cur.fetchall()
    con.close()

    #format notifications for html
    notifications = []
    for text, created_at in rows:
        t = datetime.fromisoformat(created_at).strftime("%d %b %Y, %H:%M")
        notifications.append({"text": text, "time": t})

    #load notifications page
    return render_template(
        "notifications.html",
        username=u,
        notifications=notifications
    )



@app.route("/projects")
def projects():

    #check login
    if "username" not in session:
        return redirect("/login")

    u = session["username"]

    #get team id
    team_id = _current_team_id(u)
    if not team_id:
        return redirect("/welcome")

    #today for html min date
    today = date.today().isoformat()

    con = db()
    cur = con.cursor()

    #get team owner
    cur.execute("SELECT owner FROM teams WHERE id=?", (team_id,))
    team_owner = cur.fetchone()[0]

    #decide role
    role = "owner" if team_owner == u else "member"

    #get team members
    cur.execute("SELECT username FROM team_members WHERE team_id=?", (team_id,))
    members = [r[0] for r in cur.fetchall()]

    #ensure owner is included
    if team_owner not in members:
        members.insert(0, team_owner)

    #get projects
    cur.execute("""
        SELECT id, name, description, owner
        FROM projects
        WHERE team_id=?
        ORDER BY id DESC
    """, (team_id,))
    project_rows = cur.fetchall()

    projects = []

    for pid, name, description, p_owner in project_rows:

        #get tasks
        cur.execute("""
            SELECT id, title, description, status, date_due, task_type, personal_owner
            FROM tasks
            WHERE project_id=?
            ORDER BY id DESC
        """, (pid,))
        task_rows = cur.fetchall()

        tasks = []

        for tid, title, desc, status, date_due, task_type, personal_owner in task_rows:

            days_left = None
            if date_due:
                try:
                    due = date.fromisoformat(date_due)  # YYYY-MM-DD
                    days_left = (due - date.today()).days
                except ValueError:
                    days_left = None

            #for personal tasks there may be no rows in task_assignees
            cur.execute("""
                SELECT username, completed
                FROM task_assignees
                WHERE task_id=?
            """, (tid,))
            assignees = cur.fetchall()

            tasks.append({
                "id": tid,
                "title": title,
                "description": desc,
                "status": "Done" if status == 1 else "Todo",
                "days_left": days_left,
                "assignees": assignees,
                "task_type": task_type,
                "personal_owner": personal_owner
            })

        projects.append({
            "id": pid,
            "name": name,
            "description": description,
            "owner": p_owner,
            "tasks": tasks
        })

    con.close()

    return render_template(
        "projects.html",
        username=u,
        role=role,
        members=members,
        projects=projects,
        today=today
    )



#run flask app
if __name__ == "__main__":
    app.run(debug=True)