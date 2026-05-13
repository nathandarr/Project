"""Form-handler routes that mutate state and redirect back to a page.

Covers `/accounts/*` (add / update / delete game accounts), `/profile/avatar`
(avatar upload), `/players/<id>/comments` (post comment), and
`/comments/<id>/delete` (delete comment).
"""
import os

from flask import flash, redirect, request, url_for
from werkzeug.utils import secure_filename

from app import (
    allowed_file,
    app,
    db,
    get_current_user,
    login_required,
    validate_account_payload,
    validate_comment_body,
)
from models import GameAccount, ProfileComment, User


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
    account.tags = payload["tags"]

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
