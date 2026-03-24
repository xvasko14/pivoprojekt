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


def test_post_new_event_shows_delete_link(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "delete" in response.text.lower()


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


def test_get_delete_confirm_valid_token(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    response = client.get(f"/events/{event_id}/delete?token={token}")
    assert response.status_code == 200
    assert "zmazať" in response.text.lower()


def test_get_delete_wrong_token(client, sample_event):
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}/delete?token=wrong")
    assert response.status_code == 403


def test_post_delete_valid_token(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    response = client.post(f"/events/{event_id}/delete?token={token}",
        follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_post_delete_removes_event(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    client.post(f"/events/{event_id}/delete?token={token}", follow_redirects=True)
    assert database.get_event(event_id) is None


def test_post_delete_wrong_token(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/delete?token=wrong")
    assert response.status_code == 403
