import uuid


def test_profile_update_and_password_change(client):
    # Register / seed creates an admin user on first login.
    login = client.post("/api/v1/auth/login", json={
        "email": "admin@isotopiq.dev",
        "password": "OrbitWatch-Admin-2024!",
    })
    assert login.status_code == 200

    res = client.patch("/api/v1/auth/me", json={"full_name": "Jane Doe"})
    assert res.status_code == 200
    assert res.json()["full_name"] == "Jane Doe"

    pw = client.post("/api/v1/auth/change-password", json={
        "current_password": "OrbitWatch-Admin-2024!",
        "new_password": "OrbitWatch-Admin-2025!",
    })
    assert pw.status_code == 200

    # Old password no longer works.
    old = client.post("/api/v1/auth/login", json={
        "email": "admin@isotopiq.dev",
        "password": "OrbitWatch-Admin-2024!",
    })
    assert old.status_code == 401

    new = client.post("/api/v1/auth/login", json={
        "email": "admin@isotopiq.dev",
        "password": "OrbitWatch-Admin-2025!",
    })
    assert new.status_code == 200
