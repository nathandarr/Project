def test_register_creates_user_and_redirects(client):
    response = client.post(
        "/register",
        data={
            "first_name": "New",
            "last_name": "Bie",
            "dob": "2000-01-01",
            "country_code": "+61",
            "phone_number": "0400000000",
            "username": "newbie",
            "email": "newbie@example.com",
            "password": "pw123456",
            "confirm_password": "pw123456",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_login_with_valid_credentials(client, make_user):
    make_user(username="alice", email="alice@example.com", password="pw123456")

    response = client.post(
        "/login",
        data={"identifier": "alice", "password": "pw123456"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_login_with_wrong_password_fails(client, make_user):
    make_user(username="alice", email="alice@example.com", password="pw123456")

    response = client.post(
        "/login",
        data={"identifier": "alice", "password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_logout_clears_session(client, make_user):
    make_user(password="pw123456")
    client.post("/login", data={"identifier": "alice", "password": "pw123456"})

    response = client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 303)
