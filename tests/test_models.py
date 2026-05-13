from app import User, db


def test_password_is_hashed_not_plaintext(app):
    with app.app_context():
        user = User(username="bob", email="bob@example.com")
        user.set_password("hunter2")
        db.session.add(user)
        db.session.commit()

        assert user.password_hash != "hunter2"
        assert user.check_password("hunter2") is True
        assert user.check_password("wrong") is False


def test_full_name_strips_blank_parts(app):
    with app.app_context():
        user = User(username="cat", email="c@example.com", first_name="Cat", last_name="")
        assert user.full_name == "Cat"
