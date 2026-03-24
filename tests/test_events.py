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
