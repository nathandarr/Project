"""JSON API endpoints (`/api/profile`, `/api/accounts`, `/api/stats`)."""
from flask import jsonify, request

from app import (
    app,
    db,
    get_current_user,
    login_required,
    serialize_account,
    serialize_user_profile,
    validate_account_payload,
    validate_user_profile_form,
)
from models import GameAccount


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

    source = request.get_json(silent=True) or {}
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
    account.tags = payload["tags"]

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
