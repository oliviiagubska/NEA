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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect("login.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_pw))
        user = cur.fetchone()
        conn.close()

        if user:
            session["username"] = username
            return redirect("/welcome")
        else:
            return "Login failed"

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
    
if __name__ == "__main__":
    app.run(debug=True)
