"""Direct-message chat routes (`/chat/users`, `/chat/dm/<id>`, `/chat/dm/send`)."""
from flask import jsonify, request
from sqlalchemy import func, or_

from app import app, db, get_current_user, login_required
from models import Message, User


@app.route("/chat/users", methods=["GET"])
@login_required
def chat_users():
    viewer = get_current_user()
    if viewer is None:
        return jsonify({"error": "Authentication required."}), 401

    users = (
        User.query.filter(User.id != viewer.id)
        .order_by(func.lower(User.username))
        .all()
    )

    return jsonify([{"id": user.id, "username": user.username} for user in users])


@app.route("/chat/dm/<int:user_id>", methods=["GET"])
@login_required
def chat_dm(user_id: int):
    viewer = get_current_user()
    if viewer is None:
        return jsonify({"error": "Authentication required."}), 401

    other = db.session.get(User, user_id)
    if other is None:
        return jsonify({"error": "User not found."}), 404

    messages = (
        Message.query.filter(
            or_(
                (Message.sender_id == viewer.id) & (Message.receiver_id == other.id),
                (Message.sender_id == other.id) & (Message.receiver_id == viewer.id),
            )
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return jsonify(
        [
            {
                "created_at": message.created_at.strftime("%d %b %H:%M"),
                "sender": message.sender.username,
                "content": message.content,
            }
            for message in messages
        ]
    )


@app.route("/chat/dm/send", methods=["POST"])
@login_required
def chat_dm_send():
    viewer = get_current_user()
    if viewer is None:
        return jsonify({"error": "Authentication required."}), 401

    payload = request.get_json(silent=True) or {}
    receiver_id = payload.get("receiver_id")
    content = (payload.get("content") or "").strip()

    if not isinstance(receiver_id, int):
        return jsonify({"success": False, "error": "Invalid receiver."}), 400

    if not content:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400

    if len(content) > 500:
        return jsonify({"success": False, "error": "Message too long."}), 400

    if receiver_id == viewer.id:
        return jsonify({"success": False, "error": "Cannot message yourself."}), 400

    receiver = db.session.get(User, receiver_id)
    if receiver is None:
        return jsonify({"success": False, "error": "Receiver not found."}), 404

    message = Message(sender_id=viewer.id, receiver_id=receiver.id, content=content)
    db.session.add(message)
    db.session.commit()

    return jsonify({"success": True})
