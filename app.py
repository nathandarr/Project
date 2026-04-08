from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "secret123"

VALID_USERNAME = "admin"
VALID_PASSWORD = "123456"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.")
            return render_template("login.html")

        if username == VALID_USERNAME and password == VALID_PASSWORD:
            flash("Login successful!")
            return redirect(url_for("home"))

        flash("Invalid username or password.")
        return render_template("login.html")

    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        dob = request.form.get('dob')
        email = request.form.get('email')
        country_code = request.form.get('country_code')
        phone_number = request.form.get('phone_number')

        # save to database here

        return redirect(url_for('home'))

    return render_template('register.html')


if __name__ == "__main__":
    app.run(debug=True)