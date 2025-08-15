from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = "your-secret-key"

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect("login.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cur.fetchone()
        if existing_user:
            conn.close()
            return "Username already exists"

        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pwd = request.form["password"]

        hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()

        con = sqlite3.connect("login.db")
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (uname, hashed_pwd))
        user = cur.fetchone()
        con.close()

        if user:
            session["username"] = uname
            return redirect("/welcome")
        else:
            return "Login failed"

    else:
        return render_template("login.html")


@app.route("/welcome")
def welcome():
    if "username" not in session:
        return redirect("/login")
    return render_template("welcome.html", username=session["username"])

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

@app.route("/create_team", methods=["GET","POST"])
def create_team():
    if "username" not in session:
        return redirect("/login")
    
    if request.method == "POST":
        tname = request.form["team_name"]

        con = sqlite3.connect("login.db")
        cur = con.cursor()
        cur.execute("INSERT INTO teams (name, owner) VALUES (?, ?)", (tname, session["username"]))
        con.commit()
        con.close()

        return redirect("/app")
    else:
        return render_template("create_team.html")

from datetime import datetime

from datetime import datetime

@app.route("/app")
def app_home():
    if "username" not in session:
        return redirect("/login")
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greet = "Good morning"
    elif hour < 18:
        greet = "Good afternoon"
    else:
        greet = "Good evening"
    date_str = now.strftime("%A, %d %B %Y")
    done = 68
    todo = 32
    name = session["username"]
    initials = name[:2].upper() if name else "U"

    return render_template("app_home.html",
                           username=session["username"],
                           date_today=date_str,
                           greeting=greet,
                           done=done,
                           todo=todo,
                           initials=initials)


    
if __name__ == "__main__":
    app.run(debug=True)
