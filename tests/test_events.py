import database


def test_get_new_event_form(client):
    response = client.get("/events/new")
    assert response.status_code == 200
    assert "Nový event" in response.text


def test_post_new_event_redirects_to_detail(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/events/")


def test_post_new_event_creates_event(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "U Karla" in response.text


def test_post_new_event_missing_place(client):
    response = client.post("/events/new", data={
        "place": "",
        "event_date": "2099-12-31",
        "event_time": "19:00",
    })
    assert response.status_code == 200
    assert "Nový event" in response.text  # re-shown form


def test_event_detail(client, sample_event):
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert "Hostinec U Karla" in response.text
    assert "Idem" in response.text
    assert "Neidem" in response.text


def test_event_detail_not_found(client):
    response = client.get("/events/nonexistent-id")
    assert response.status_code == 404


def test_get_delete_confirm(client, sample_event):
    """Anyone can access the delete confirmation page."""
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}/delete")
    assert response.status_code == 200
    assert "zmazať" in response.text.lower()


def test_get_delete_confirm_nonexistent(client):
    response = client.get("/events/nonexistent-id/delete")
    assert response.status_code == 404


def test_post_delete_redirects_home(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_post_delete_removes_event(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/delete", follow_redirects=True)
    assert database.get_event(event_id) is None


def test_post_delete_nonexistent(client):
    response = client.post("/events/nonexistent-id/delete")
    assert response.status_code == 404
