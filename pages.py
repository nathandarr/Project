"""
Page navigation routes.

This module owns every route whose primary job is to *render a page*
(GET handlers) plus the matching POST handlers that produce a redirect
back to a page (login, register, profile edit). Action endpoints
(/accounts/*, /chat/*, /api/*) stay in app.py.

The routes are attached to the existing Flask `app` via the @app.route
decorator — app.py imports this module near the bottom (after the app,
db, models, and helpers are defined) so all the symbols below are ready
when the decorators run.
"""
from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from app import (
    ALLOWED_TAGS,
    GAMES,
    app,
    build_user_summary,
    db,
    get_current_user,
    login_required,
    validate_user_profile_form,
)
from models import GameAccount, ProfileComment, User


def _build_leaderboard_rows(game_name: str) -> list[dict]:
    """Return ranked GameAccount rows for one game, highest tier first.

    Sort key: rank tier (using GAMES[game].index as the numeric position) DESC,
    then level DESC, then account_name ASC as the final tiebreaker.
    Accounts whose `rank` value isn't in GAMES[game] (legacy / free-typed)
    get tier -1 so they sink to the bottom rather than crashing the sort.
    """
    rank_order = GAMES.get(game_name, [])
    rank_position = {rank: index for index, rank in enumerate(rank_order)}

    accounts = (
        GameAccount.query.filter_by(game_name=game_name)
        .join(User, GameAccount.user_id == User.id)
        .filter(User.is_banned.is_(False))
        .all()
    )

    rows = []
    for account in accounts:
        tier = rank_position.get(account.rank, -1)
        rows.append({
            "account": account,
            "user": account.user,
            "tier": tier,
            "tier_label": account.rank,
        })

    rows.sort(
        key=lambda row: (-row["tier"], -row["account"].level, row["account"].account_name.lower())
    )

    for index, row in enumerate(rows, start=1):
        row["position"] = index

    return rows


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
            if user.is_banned:
                flash("This account has been banned. Contact an administrator.", "danger")
                return render_template("login.html")
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
        allowed_tags=ALLOWED_TAGS,
        games=GAMES,
    )


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


@app.route("/leaderboard")
@login_required
def leaderboard():
    viewer = get_current_user()
    if viewer is None:
        flash("Please log in to access that page.", "warning")
        return redirect(url_for("login"))

    games_list = list(GAMES.keys())
    requested_game = request.args.get("game", "").strip()
    selected_game = requested_game if requested_game in GAMES else games_list[0]

    rows = _build_leaderboard_rows(selected_game)

    return render_template(
        "leaderboard.html",
        viewer=viewer,
        games=games_list,
        selected_game=selected_game,
        rank_tiers=GAMES[selected_game],
        rows=rows,
        total_entries=len(rows),
    )
