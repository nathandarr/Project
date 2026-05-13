def login(client, username, password):
    return client.post(
        "/login",
        data={"identifier": username, "password": password},
    )


def test_chat_users_excludes_self(client, make_user):
    make_user(username="alice", email="a@x.com", password="pw123456")
    make_user(username="bob", email="b@x.com", password="pw123456")

    login(client, "alice", "pw123456")
    response = client.get("/chat/users")

    assert response.status_code == 200
    usernames = [u["username"] for u in response.get_json()]
    assert "bob" in usernames
    assert "alice" not in usernames


def test_chat_users_requires_login(client):
    response = client.get("/chat/users")
    assert response.status_code == 401


def test_send_and_read_dm(client, make_user):
    make_user(username="alice", email="a@x.com", password="pw123456")
    bob_id = make_user(username="bob", email="b@x.com", password="pw123456")

    login(client, "alice", "pw123456")
    send = client.post(
        "/chat/dm/send",
        json={"receiver_id": bob_id, "content": "hello bob"},
    )
    assert send.status_code == 200
    assert send.get_json() == {"success": True}

    read = client.get(f"/chat/dm/{bob_id}")
    assert read.status_code == 200
    body = read.get_json()
    assert len(body) == 1
    assert body[0]["content"] == "hello bob"
    assert body[0]["sender"] == "alice"


def test_send_dm_rejects_empty(client, make_user):
    make_user(username="alice", email="a@x.com", password="pw123456")
    bob_id = make_user(username="bob", email="b@x.com", password="pw123456")

    login(client, "alice", "pw123456")
    response = client.post(
        "/chat/dm/send",
        json={"receiver_id": bob_id, "content": "   "},
    )
    assert response.status_code == 400


def test_send_dm_rejects_self(client, make_user):
    alice_id = make_user(username="alice", email="a@x.com", password="pw123456")

    login(client, "alice", "pw123456")
    response = client.post(
        "/chat/dm/send",
        json={"receiver_id": alice_id, "content": "talking to myself"},
    )
    assert response.status_code == 400
