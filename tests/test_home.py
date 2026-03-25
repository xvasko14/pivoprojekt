def test_home_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "DRMF Pivo" in response.text


def test_home_shows_upcoming_event(client, sample_event):
    import database
    database.create_event("Future Pub", "2099-12-31", "19:00", None)
    response = client.get("/")
    assert response.status_code == 200
    assert "Future Pub" in response.text


def test_home_shows_history(client):
    import database
    database.create_event("Past Pub", "2000-01-01", "19:00", None)
    response = client.get("/")
    assert response.status_code == 200
    assert "Past Pub" in response.text
