import os
import sys
from datetime import date
from functools import wraps
from typing import Any

# Allow `python app.py` to coexist with companion modules that do
# `from app import ...`. Without this alias Python loads app.py twice
# (once as __main__, once as `app`), and the second load races with
# the still-importing first one — breaking `from models import ...` etc.
sys.modules["app"] = sys.modules[__name__]

from flask import Flask, flash, jsonify, redirect, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, or_, text

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")

os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DB_PATH}"
)
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
ALLOWED_TAGS = ["Casual", "LFG", "New Player", "Veteran", "Coach", "Streamer", "Solo", "Tryhard"]

# Supported games and their ordered rank tiers (low → high).
# Order matters: the index in each list is the rank's numeric position,
# which is what a future leaderboard sort can use.
GAMES: dict[str, list[str]] = {
    "Valorant":          ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"],
    "League of Legends": ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond", "Master", "Grandmaster", "Challenger"],
    "Counter-Strike 2":  ["Silver I", "Silver II", "Silver Elite", "Gold Nova", "Master Guardian", "DMG", "Legendary Eagle", "LEM", "Supreme", "Global Elite"],
    "Overwatch 2":       ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Top 500"],
    "Apex Legends":      ["Rookie", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Apex Predator"],
    "Dota 2":            ["Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"],
    "Rocket League":     ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Champion", "Grand Champion", "Supersonic Legend"],
    "Fortnite":          ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Elite", "Champion", "Unreal"],
}


# Models live in models.py — imported as a side effect so SQLAlchemy
# registers the classes against `db` before db.create_all() runs below.
from models import GameAccount, User  # noqa: E402  (used by helpers below)


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
    if "is_banned" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN is_banned BOOLEAN NOT NULL DEFAULT 0")
    
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


def add_missing_game_account_columns() -> None:
    inspector = inspect(db.engine)
    if "game_accounts" not in set(inspector.get_table_names()):
        return

    columns = {c["name"] for c in inspector.get_columns("game_accounts")}
    if "tags" in columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE game_accounts ADD COLUMN tags VARCHAR(200) NOT NULL DEFAULT ''"))

def add_missing_comment_likes_table() -> None:
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    if "comment_likes" not in existing_tables:
        with db.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE comment_likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    comment_id INTEGER NOT NULL REFERENCES profile_comments(id),
                    vote_type VARCHAR(10) NOT NULL DEFAULT 'up'
                )
            """))
    else:
        columns = {c["name"] for c in inspector.get_columns("comment_likes")}
        if "vote_type" not in columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE comment_likes ADD COLUMN vote_type VARCHAR(10) NOT NULL DEFAULT 'up'"))

with app.app_context():
    db.create_all()
    add_missing_user_profile_columns()
    add_missing_game_account_columns()
    add_missing_comment_likes_table()


def get_current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    # Banned users are treated as logged-out — get_current_user returns None,
    # @login_required clears their session, and they're sent to /login.
    if user is not None and user.is_banned:
        return None
    return user


def is_api_request() -> bool:
    return request.path.startswith("/api/") or request.path.startswith("/chat/")


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


def admin_required(view_func):
    """Like login_required, but also requires user.is_admin."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            session.clear()
            if is_api_request():
                return jsonify({"error": "Authentication required."}), 401
            flash("Please log in to access that page.", "warning")
            return redirect(url_for("login"))
        if not user.is_admin:
            if is_api_request():
                return jsonify({"error": "Admin access required."}), 403
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}

@app.template_filter("get_upvotes")
def get_upvotes(comment_id: int) -> int:
    from models import CommentLike
    return CommentLike.query.filter_by(comment_id=comment_id, vote_type="up").count()

@app.template_filter("get_downvotes")
def get_downvotes(comment_id: int) -> int:
    from models import CommentLike
    return CommentLike.query.filter_by(comment_id=comment_id, vote_type="down").count()

@app.template_filter("user_vote")
def user_vote(user_id: int, comment_id: int) -> str | None:
    from models import CommentLike
    vote = CommentLike.query.filter_by(user_id=user_id, comment_id=comment_id).first()
    return vote.vote_type if vote else None

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
        "tags": account.tag_list,
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

    # Tags: HTML form sends multiple values when checkboxes share a name.
    # request.form (a MultiDict) provides .getlist; JSON payloads pass a list.
    if hasattr(source, "getlist"):
        raw_tags = source.getlist("tags")
    else:
        raw = source.get("tags", [])
        raw_tags = raw if isinstance(raw, list) else [raw]

    seen: list[str] = []
    for tag in raw_tags:
        clean = str(tag).strip()
        if clean and clean in ALLOWED_TAGS and clean not in seen:
            seen.append(clean)
    tags = ",".join(seen)

    errors: list[str] = []

    if not game_name:
        errors.append("Game name is required.")
    elif game_name not in GAMES:
        errors.append(f"Game must be one of: {', '.join(GAMES.keys())}.")
    if not account_name:
        errors.append("Account name is required.")
    if region not in ALLOWED_REGIONS:
        errors.append(f"Region must be one of: {', '.join(sorted(ALLOWED_REGIONS))}.")
    if not rank:
        errors.append("Rank is required.")
    elif game_name in GAMES and rank not in GAMES[game_name]:
        errors.append(f"Rank '{rank}' is not valid for {game_name}.")
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
        "tags": tags,
    }

    return payload, errors

# Register routes from companion modules. Imported as side effects so the
# @app.route decorators inside each module attach to this app.
import pages    # noqa: E402, F401
import actions  # noqa: E402, F401
import chat     # noqa: E402, F401
import api      # noqa: E402, F401
import admin    # noqa: E402, F401


if __name__ == "__main__":
    app.run(debug=True)
