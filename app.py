from __future__ import annotations

import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, ForeignKey, func, or_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# IMPORTANT:
# Change this in production and preferably load it from an environment variable.
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")

os.makedirs(INSTANCE_DIR, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    game_accounts: Mapped[list["GameAccount"]] = relationship(
        "GameAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="GameAccount.id.desc()"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class GameAccount(db.Model):
    __tablename__ = "game_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="OCE")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rank: Mapped[str] = mapped_column(String(50), nullable=False, default="Unranked")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="game_accounts")


with app.app_context():
    db.create_all()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access that page.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
    return {"current_user": user}


@app.route("/")
def mainmenu():
    return render_template("index.html")


@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter both username/email and password.", "danger")
            return render_template("login.html")

        normalized_identifier = identifier.lower()

        user = User.query.filter(
            or_(
                func.lower(User.username) == normalized_identifier,
                func.lower(User.email) == normalized_identifier,
            )
        ).first()

        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        dob = request.form.get("dob", "").strip()
        email = request.form.get("email", "").strip().lower()
        country_code = request.form.get("country_code", "").strip()
        phone_number = request.form.get("phone_number", "").strip()

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors: list[str] = []

        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not dob:
            errors.append("Date of birth is required.")
        if not country_code:
            errors.append("Country code is required.")
        if not phone_number:
            errors.append("Phone number is required.")

        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters long.")
        elif "@" in username:
            errors.append("Username cannot contain @.")

        if not email:
            errors.append("Email is required.")
        elif "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        if password != confirm_password:
            errors.append("Passwords do not match.")

        normalized_username = username.lower()

        existing_username = User.query.filter(
            func.lower(User.username) == normalized_username
        ).first()
        if existing_username:
            errors.append(
                "That username is already taken. Please sign in or choose a different username."
            )

        existing_email = User.query.filter(
            func.lower(User.email) == email
        ).first()
        if existing_email:
            errors.append(
                "That email is already registered. Please sign in or use a different email address."
            )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = db.session.get(User, session["user_id"])
    accounts = GameAccount.query.filter_by(user_id=user.id).order_by(GameAccount.id.desc()).all()

    total_accounts = len(accounts)
    total_games = len({account.game_name.lower() for account in accounts})
    highest_level = max((account.level for account in accounts), default=0)

    return render_template(
        "dashboard.html",
        user=user,
        accounts=accounts,
        total_accounts=total_accounts,
        total_games=total_games,
        highest_level=highest_level
    )


@app.route("/accounts/add", methods=["POST"])
@login_required
def add_account():
    user_id = session["user_id"]

    game_name = request.form.get("game_name", "").strip()
    account_name = request.form.get("account_name", "").strip()
    region = request.form.get("region", "").strip()
    level_raw = request.form.get("level", "").strip()
    rank = request.form.get("rank", "").strip()
    status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()

    errors: list[str] = []

    if not game_name:
        errors.append("Game name is required.")
    if not account_name:
        errors.append("Account name is required.")
    if not region:
        errors.append("Region is required.")
    if not rank:
        errors.append("Rank is required.")
    if not status:
        errors.append("Status is required.")

    try:
        level = int(level_raw)
        if level < 1:
            errors.append("Level must be at least 1.")
    except ValueError:
        errors.append("Level must be a valid number.")
        level = 1

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("dashboard"))

    account = GameAccount(
        game_name=game_name,
        account_name=account_name,
        region=region,
        level=level,
        rank=rank,
        status=status,
        notes=notes,
        user_id=user_id,
    )

    db.session.add(account)
    db.session.commit()

    flash("Game account added successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/accounts/update/<int:account_id>", methods=["POST"])
@login_required
def update_account(account_id: int):
    user_id = session["user_id"]
    account = GameAccount.query.filter_by(id=account_id, user_id=user_id).first()

    if not account:
        flash("Account not found.", "danger")
        return redirect(url_for("dashboard"))

    game_name = request.form.get("game_name", "").strip()
    account_name = request.form.get("account_name", "").strip()
    region = request.form.get("region", "").strip()
    level_raw = request.form.get("level", "").strip()
    rank = request.form.get("rank", "").strip()
    status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()

    errors: list[str] = []

    if not game_name:
        errors.append("Game name is required.")
    if not account_name:
        errors.append("Account name is required.")
    if not region:
        errors.append("Region is required.")
    if not rank:
        errors.append("Rank is required.")
    if not status:
        errors.append("Status is required.")

    try:
        level = int(level_raw)
        if level < 1:
            errors.append("Level must be at least 1.")
    except ValueError:
        errors.append("Level must be a valid number.")
        level = account.level

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("dashboard", edit=account_id))

    account.game_name = game_name
    account.account_name = account_name
    account.region = region
    account.level = level
    account.rank = rank
    account.status = status
    account.notes = notes

    db.session.commit()

    flash("Game account updated successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/accounts/delete/<int:account_id>", methods=["POST"])
@login_required
def delete_account(account_id: int):
    user_id = session["user_id"]
    account = GameAccount.query.filter_by(id=account_id, user_id=user_id).first()

    if not account:
        flash("Account not found.", "danger")
        return redirect(url_for("dashboard"))

    db.session.delete(account)
    db.session.commit()

    flash("Game account deleted successfully.", "info")
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)