"""Admin dashboard routes — list users, ban / promote / delete users,
delete any game account.

All routes require `current_user.is_admin`. The decorator `admin_required`
lives in app.py.
"""
from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func

from app import admin_required, app, db, get_current_user
from models import GameAccount, Message, ProfileComment, User


@app.route("/admin")
@admin_required
def admin_dashboard():
    users = User.query.order_by(func.lower(User.username)).all()
    accounts = (
        GameAccount.query.join(User)
        .order_by(func.lower(User.username), GameAccount.id.desc())
        .all()
    )
    return render_template(
        "admin.html",
        users=users,
        accounts=accounts,
        viewer=get_current_user(),
    )


@app.route("/admin/users/<int:user_id>/toggle-ban", methods=["POST"])
@admin_required
def admin_toggle_ban(user_id: int):
    target = db.session.get(User, user_id)
    if target is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    viewer = get_current_user()
    if target.id == viewer.id:
        flash("You cannot ban yourself.", "warning")
        return redirect(url_for("admin_dashboard"))

    target.is_banned = not target.is_banned
    db.session.commit()
    flash(
        f"User '{target.username}' has been {'banned' if target.is_banned else 'unbanned'}.",
        "success" if not target.is_banned else "info",
    )
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def admin_toggle_admin(user_id: int):
    target = db.session.get(User, user_id)
    if target is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    viewer = get_current_user()
    if target.id == viewer.id:
        flash("You cannot remove your own admin role.", "warning")
        return redirect(url_for("admin_dashboard"))

    target.is_admin = not target.is_admin
    db.session.commit()
    flash(
        f"'{target.username}' is now {'an admin' if target.is_admin else 'a regular user'}.",
        "info",
    )
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id: int):
    target = db.session.get(User, user_id)
    if target is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    viewer = get_current_user()
    if target.id == viewer.id:
        flash("You cannot delete your own account from here.", "warning")
        return redirect(url_for("admin_dashboard"))

    # Manually clean up dependents that don't have ON DELETE CASCADE.
    # game_accounts cascade via the existing relationship — they'll go
    # automatically when we delete the user.
    ProfileComment.query.filter(
        (ProfileComment.author_id == target.id)
        | (ProfileComment.profile_user_id == target.id)
    ).delete(synchronize_session=False)

    Message.query.filter(
        (Message.sender_id == target.id) | (Message.receiver_id == target.id)
    ).delete(synchronize_session=False)

    username = target.username
    db.session.delete(target)
    db.session.commit()

    flash(f"User '{username}' deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/accounts/<int:account_id>/delete", methods=["POST"])
@admin_required
def admin_delete_account(account_id: int):
    account = db.session.get(GameAccount, account_id)
    if account is None:
        flash("Game account not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    label = f"{account.game_name} / {account.account_name}"
    db.session.delete(account)
    db.session.commit()

    flash(f"Game account '{label}' deleted.", "success")
    return redirect(url_for("admin_dashboard"))
