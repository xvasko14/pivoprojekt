# tests/test_rsvp.py
import database


def test_rsvp_going(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/rsvp",
        data={"name": "Marek", "going": "true"},
        follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/events/{event_id}"


def test_rsvp_shows_name_on_detail(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "true"})
    response = client.get(f"/events/{event_id}")
    assert "Marek" in response.text


def test_rsvp_overwrites(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "true"})
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "false"})
    rsvps = database.get_rsvps(event_id)
    assert len(rsvps) == 1
    assert rsvps[0]["going"] == 0


def test_rsvp_empty_name(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/rsvp",
        data={"name": "", "going": "true"},
        follow_redirects=True)
    assert response.status_code == 200
    assert "meno" in response.text.lower()


def test_rsvp_invalid_event(client):
    response = client.post("/events/nonexistent/rsvp",
        data={"name": "Marek", "going": "true"})
    assert response.status_code == 404
