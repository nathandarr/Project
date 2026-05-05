import os
from datetime import date, datetime
from functools import wraps
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func, inspect, or_, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")

os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

ALLOWED_REGIONS = {"OCE", "Asia", "EU", "NA"}
ALLOWED_STATUSES = {"Active", "Inactive"}


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    game_accounts: Mapped[list["GameAccount"]] = relationship(
        "GameAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="GameAccount.id.desc()",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        return f"{first} {last}".strip()


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

class ProfileComment(db.Model):
    __tablename__ = "profile_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    profile_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    profile_user: Mapped["User"] = relationship("User", foreign_keys=[profile_user_id])


def add_missing_user_profile_columns() -> None:
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    if "users" not in existing_tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "first_name" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN first_name VARCHAR(80)")
    if "last_name" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN last_name VARCHAR(80)")
    if "dob" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN dob DATE")
    if "country_code" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN country_code VARCHAR(10)")
    if "phone_number" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(30)")
    if "created_at" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN created_at DATETIME")
    if "updated_at" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN updated_at DATETIME")
    if "avatar_path" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255)")
    
    if not statements:
        return

    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        connection.execute(
            text(
                """
                UPDATE users
                SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
                """
            )
        )


with app.app_context():
    db.create_all()
    add_missing_user_profile_columns()


def get_current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def is_api_request() -> bool:
    return request.path.startswith("/api/")


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            session.clear()

            if is_api_request():
                return jsonify({"error": "Authentication required."}), 401

            flash("Please log in to access that page.", "warning")
            return redirect(url_for("login"))

        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


def parse_dob(raw_value: str) -> date | None:
    raw_value = raw_value.strip()
    if not raw_value:
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        return None


def validate_user_profile_form(
    form_data,
    current_user_id: int | None = None,
    require_password: bool = False,
):
    first_name = form_data.get("first_name", "").strip()
    last_name = form_data.get("last_name", "").strip()
    dob_raw = form_data.get("dob", "").strip()
    country_code = form_data.get("country_code", "").strip()
    phone_number = form_data.get("phone_number", "").strip()
    username = form_data.get("username", "").strip()
    email = form_data.get("email", "").strip().lower()

    current_password = form_data.get("current_password", "")
    password = form_data.get("password", "")
    confirm_password = form_data.get("confirm_password", "")

    errors: list[str] = []

    if not first_name:
        errors.append("First name is required.")

    if not last_name:
        errors.append("Last name is required.")

    dob = parse_dob(dob_raw)
    if dob is None:
        errors.append("Please enter a valid date of birth.")
    elif dob > date.today():
        errors.append("Date of birth cannot be in the future.")

    if not country_code:
        errors.append("Country code is required.")
    elif not country_code.startswith("+"):
        errors.append("Country code must start with +.")

    digits_only = "".join(character for character in phone_number if character.isdigit())
    if not phone_number:
        errors.append("Phone number is required.")
    elif len(digits_only) < 6:
        errors.append("Phone number looks too short.")

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

    username_query = User.query.filter(func.lower(User.username) == username.lower())
    email_query = User.query.filter(func.lower(User.email) == email)

    if current_user_id is not None:
        username_query = username_query.filter(User.id != current_user_id)
        email_query = email_query.filter(User.id != current_user_id)

    if username_query.first():
        errors.append("That username is already taken.")

    if email_query.first():
        errors.append("That email is already registered.")

    new_password_to_set: str | None = None

    if require_password:
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        if password != confirm_password:
            errors.append("Passwords do not match.")

        if password and len(password) >= 8 and password == confirm_password:
            new_password_to_set = password
    else:
        wants_password_change = bool(current_password or password or confirm_password)

        if wants_password_change:
            if not current_password:
                errors.append("Current password is required to change your password.")

            if not password:
                errors.append("New password is required.")
            elif len(password) < 8:
                errors.append("New password must be at least 8 characters long.")

            if password != confirm_password:
                errors.append("New passwords do not match.")

            if password and len(password) >= 8 and password == confirm_password:
                new_password_to_set = password

    cleaned_data = {
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "country_code": country_code,
        "phone_number": phone_number,
        "username": username,
        "email": email,
    }

    return cleaned_data, new_password_to_set, current_password, errors

def build_user_summary(user: User) -> dict[str, Any]:
    accounts = (
        GameAccount.query.filter_by(user_id=user.id)
        .order_by(GameAccount.level.desc(), GameAccount.id.desc())
        .all()
    )

    featured_account = accounts[0] if accounts else None

    return {
        "user": user,
        "total_accounts": len(accounts),
        "total_games": len({account.game_name.lower() for account in accounts}),
        "highest_level": max((account.level for account in accounts), default=0),
        "featured_account": featured_account,
    }


def validate_comment_body(raw_body: str) -> tuple[str, list[str]]:
    body = raw_body.strip()
    errors: list[str] = []

    if not body:
        errors.append("Comment cannot be empty.")
    elif len(body) > 500:
        errors.append("Comment must be 500 characters or less.")

    return body, errors


def serialize_account(account: GameAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "game_name": account.game_name,
        "account_name": account.account_name,
        "region": account.region,
        "level": account.level,
        "rank": account.rank,
        "status": account.status,
        "notes": account.notes,
        "user_id": account.user_id,
    }


def serialize_user_profile(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "dob": user.dob.isoformat() if user.dob else None,
        "country_code": user.country_code,
        "phone_number": user.phone_number,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def validate_account_payload(source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    game_name = str(source.get("game_name", "")).strip()
    account_name = str(source.get("account_name", "")).strip()
    region = str(source.get("region", "")).strip()
    level_raw = source.get("level", "")
    rank = str(source.get("rank", "")).strip()
    status = str(source.get("status", "")).strip()
    notes = str(source.get("notes", "")).strip()

    errors: list[str] = []

    if not game_name:
        errors.append("Game name is required.")
    if not account_name:
        errors.append("Account name is required.")
    if region not in ALLOWED_REGIONS:
        errors.append(f"Region must be one of: {', '.join(sorted(ALLOWED_REGIONS))}.")
    if not rank:
        errors.append("Rank is required.")
    if status not in ALLOWED_STATUSES:
        errors.append(f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}.")

    try:
        level = int(level_raw)
        if level < 1:
            errors.append("Level must be at least 1.")
    except (TypeError, ValueError):
        level = 1
        errors.append("Level must be a valid number.")

    if len(notes) > 500:
        errors.append("Notes must be 500 characters or less.")

    payload = {
        "game_name": game_name,
        "account_name": account_name,
        "region": region,
        "level": level,
        "rank": rank,
        "status": status,
        "notes": notes,
    }

    return payload, errors

def build_user_summary(user: User) -> dict[str, Any]:
    accounts = (
        GameAccount.query.filter_by(user_id=user.id)
        .order_by(GameAccount.level.desc(), GameAccount.id.desc())
        .all()
    )

    featured_account = accounts[0] if accounts else None

    return {
        "user": user,
        "total_accounts": len(accounts),
        "total_games": len({account.game_name.lower() for account in accounts}),
        "highest_level": max((account.level for account in accounts), default=0),
        "featured_account": featured_account,
    }


def validate_comment_body(raw_body: str) -> tuple[str, list[str]]:
    body = raw_body.strip()
    errors: list[str] = []

    if not body:
        errors.append("Comment cannot be empty.")
    elif len(body) > 500:
        errors.append("Comment must be 500 characters or less.")

    return body, errors



@app.route("/")
def mainmenu():
    return render_template("index.html")


@app.route("/home")
def home():
    return redirect(url_for("mainmenu"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user() is not None:
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
    if get_current_user() is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        cleaned_data, new_password, _, errors = validate_user_profile_form(
            request.form,
            current_user_id=None,
            require_password=True,
        )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html")

        if new_password is None:
            flash("Password is required.", "danger")
            return render_template("register.html")

        user = User(
            first_name=cleaned_data["first_name"],
            last_name=cleaned_data["last_name"],
            dob=cleaned_data["dob"],
            country_code=cleaned_data["country_code"],
            phone_number=cleaned_data["phone_number"],
            username=cleaned_data["username"],
            email=cleaned_data["email"],
        )
        user.set_password(new_password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if user is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    edit_id = request.args.get("edit", type=int)
    editing_account = None

    if edit_id is not None:
        editing_account = GameAccount.query.filter_by(id=edit_id, user_id=user.id).first()
        if editing_account is None:
            flash("Account not found.", "danger")
            return redirect(url_for("dashboard"))

    accounts = (
        GameAccount.query.filter_by(user_id=user.id)
        .order_by(GameAccount.id.desc())
        .all()
    )

    total_accounts = len(accounts)
    total_games = len({account.game_name.lower() for account in accounts})
    highest_level = max((account.level for account in accounts), default=0)

    return render_template(
        "dashboard.html",
        user=user,
        accounts=accounts,
        total_accounts=total_accounts,
        total_games=total_games,
        highest_level=highest_level,
        editing_account=editing_account,
    )


@app.route("/accounts/add", methods=["POST"])
@login_required
def add_account():
    user = get_current_user()
    if user is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    payload, errors = validate_account_payload(request.form)

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("dashboard"))

    account = GameAccount(user_id=user.id, **payload)
    db.session.add(account)
    db.session.commit()

    flash("Game account added successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/accounts/update/<int:account_id>", methods=["POST"])
@login_required
def update_account(account_id: int):
    user = get_current_user()
    if user is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    account = GameAccount.query.filter_by(id=account_id, user_id=user.id).first()
    if account is None:
        flash("Account not found.", "danger")
        return redirect(url_for("dashboard"))

    payload, errors = validate_account_payload(request.form)

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("dashboard", edit=account_id))

    account.game_name = payload["game_name"]
    account.account_name = payload["account_name"]
    account.region = payload["region"]
    account.level = payload["level"]
    account.rank = payload["rank"]
    account.status = payload["status"]
    account.notes = payload["notes"]

    db.session.commit()

    flash("Game account updated successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/accounts/delete/<int:account_id>", methods=["POST"])
@login_required
def delete_account(account_id: int):
    user = get_current_user()
    if user is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    account = GameAccount.query.filter_by(id=account_id, user_id=user.id).first()
    if account is None:
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
    return redirect(url_for("mainmenu"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = db.session.get(User, session["user_id"])

    if user is None:
        session.clear()
        flash("Please log in again.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        cleaned_data, new_password, current_password, errors = validate_user_profile_form(
            request.form,
            current_user_id=user.id,
            require_password=False,
        )

        wants_password_change = bool(
            request.form.get("current_password", "")
            or request.form.get("password", "")
            or request.form.get("confirm_password", "")
        )

        if wants_password_change and not user.check_password(current_password):
            errors.append("Current password is incorrect.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("profile.html", user=user)

        user.first_name = cleaned_data["first_name"]
        user.last_name = cleaned_data["last_name"]
        user.dob = cleaned_data["dob"]
        user.country_code = cleaned_data["country_code"]
        user.phone_number = cleaned_data["phone_number"]
        user.username = cleaned_data["username"]
        user.email = cleaned_data["email"]

        if new_password:
            user.set_password(new_password)

        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)

@app.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    if "avatar" not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for("profile"))

    file = request.files["avatar"]

    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("profile"))

    if not allowed_file(file.filename):
        flash("Only PNG, JPG, GIF and WEBP files are allowed.", "danger")
        return redirect(url_for("profile"))

    filename = secure_filename(f"user_{user.id}_{file.filename}")
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    user.avatar_path = f"uploads/{filename}"
    db.session.commit()

    flash("Profile picture updated!", "success")
    return redirect(url_for("profile"))

@app.route("/players")
@login_required
def players():
    current_user = get_current_user()
    if current_user is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    users = (
        User.query.filter(User.id != current_user.id)
        .order_by(func.lower(User.username))
        .all()
    )

    player_cards = [build_user_summary(user) for user in users]

    return render_template(
        "players.html",
        current_user=current_user,
        players=player_cards,
    )


@app.route("/players/<int:user_id>")
@login_required
def public_profile(user_id: int):
    viewer = get_current_user()
    if viewer is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    profile_user = db.session.get(User, user_id)
    if profile_user is None:
        flash("User not found.", "danger")
        return redirect(url_for("players"))

    accounts = (
        GameAccount.query.filter_by(user_id=profile_user.id)
        .order_by(GameAccount.level.desc(), GameAccount.id.desc())
        .all()
    )

    comments = (
        ProfileComment.query.filter_by(profile_user_id=profile_user.id)
        .order_by(ProfileComment.created_at.desc())
        .all()
    )

    total_accounts = len(accounts)
    total_games = len({account.game_name.lower() for account in accounts})
    highest_level = max((account.level for account in accounts), default=0)

    return render_template(
        "public_profile.html",
        viewer=viewer,
        profile_user=profile_user,
        accounts=accounts,
        comments=comments,
        total_accounts=total_accounts,
        total_games=total_games,
        highest_level=highest_level,
    )


@app.route("/players/<int:user_id>/comments", methods=["POST"])
@login_required
def add_profile_comment(user_id: int):
    viewer = get_current_user()
    if viewer is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    profile_user = db.session.get(User, user_id)
    if profile_user is None:
        flash("User not found.", "danger")
        return redirect(url_for("players"))

    if viewer.id == profile_user.id:
        flash("You cannot comment on your own public profile.", "warning")
        return redirect(url_for("public_profile", user_id=user_id))

    body, errors = validate_comment_body(request.form.get("body", ""))

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("public_profile", user_id=user_id))

    comment = ProfileComment(
        body=body,
        author_id=viewer.id,
        profile_user_id=profile_user.id,
    )

    db.session.add(comment)
    db.session.commit()

    flash("Comment added successfully!", "success")
    return redirect(url_for("public_profile", user_id=user_id))


@app.route("/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_profile_comment(comment_id: int):
    viewer = get_current_user()
    if viewer is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    comment = db.session.get(ProfileComment, comment_id)
    if comment is None:
        flash("Comment not found.", "danger")
        return redirect(url_for("players"))

    if viewer.id not in {comment.author_id, comment.profile_user_id}:
        flash("You are not allowed to delete that comment.", "danger")
        return redirect(url_for("public_profile", user_id=comment.profile_user_id))

    profile_user_id = comment.profile_user_id

    db.session.delete(comment)
    db.session.commit()

    flash("Comment deleted successfully.", "info")
    return redirect(url_for("public_profile", user_id=profile_user_id))

@app.route("/api/profile", methods=["PUT"])
@login_required
def api_update_profile():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    source = request.get_json(silent=True) or {}

    cleaned_data, new_password, current_password, errors = validate_user_profile_form(
        source,
        current_user_id=user.id,
        require_password=False,
    )

    wants_password_change = bool(
        source.get("current_password", "")
        or source.get("password", "")
        or source.get("confirm_password", "")
    )

    if wants_password_change and not user.check_password(current_password):
        errors.append("Current password is incorrect.")

    if errors:
        return jsonify({"errors": errors}), 400

    user.first_name = cleaned_data["first_name"]
    user.last_name = cleaned_data["last_name"]
    user.dob = cleaned_data["dob"]
    user.country_code = cleaned_data["country_code"]
    user.phone_number = cleaned_data["phone_number"]
    user.username = cleaned_data["username"]
    user.email = cleaned_data["email"]

    if new_password:
        user.set_password(new_password)

    db.session.commit()

    return jsonify(
        {
            "message": "Profile updated successfully!",
            "profile": serialize_user_profile(user),
        }
    )


# ---------------------------
# Optional JSON API endpoints
# ---------------------------

@app.route("/api/accounts", methods=["GET"])
@login_required
def api_get_accounts():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    accounts = (
        GameAccount.query.filter_by(user_id=user.id)
        .order_by(GameAccount.id.desc())
        .all()
    )
    return jsonify([serialize_account(account) for account in accounts])


@app.route("/api/stats", methods=["GET"])
@login_required
def api_get_stats():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    accounts = GameAccount.query.filter_by(user_id=user.id).all()

    return jsonify(
        {
            "total_accounts": len(accounts),
            "total_games": len({account.game_name.lower() for account in accounts}),
            "highest_level": max((account.level for account in accounts), default=0),
        }
    )


@app.route("/api/accounts", methods=["POST"])
@login_required
def api_create_account():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    source = request.get_json(silent=True) or {}
    payload, errors = validate_account_payload(source)

    if errors:
        return jsonify({"errors": errors}), 400

    account = GameAccount(user_id=user.id, **payload)
    db.session.add(account)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Game account added successfully!",
                "account": serialize_account(account),
            }
        ),
        201,
    )


@app.route("/api/accounts/<int:account_id>", methods=["PUT"])
@login_required
def api_update_account(account_id: int):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    account = GameAccount.query.filter_by(id=account_id, user_id=user.id).first()
    if account is None:
        return jsonify({"error": "Account not found."}), 404

    source = request.get_json(silent=True) or 
    payload, errors = validate_account_payload(source)

    if errors:
        return jsonify({"errors": errors}), 400

    account.game_name = payload["game_name"]
    account.account_name = payload["account_name"]
    account.region = payload["region"]
    account.level = payload["level"]
    account.rank = payload["rank"]
    account.status = payload["status"]
    account.notes = payload["notes"]

    db.session.commit()

    return jsonify(
        {
            "message": "Game account updated successfully!",
            "account": serialize_account(account),
        }
    )


@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
@login_required
def api_delete_account(account_id: int):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    account = GameAccount.query.filter_by(id=account_id, user_id=user.id).first()
    if account is None:
        return jsonify({"error": "Account not found."}), 404

    db.session.delete(account)
    db.session.commit()

    return jsonify({"message": "Game account deleted successfully."})

if __name__ == "__main__":
    app.run(debug=True)
