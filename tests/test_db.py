import database


def test_create_and_get_event():
    result = database.create_event("U Karla", "2099-12-31", "19:00", "Test")
    event = database.get_event(result["id"])
    assert event is not None
    assert event["place"] == "U Karla"
    assert event["delete_token"] == result["delete_token"]


def test_get_event_not_found():
    assert database.get_event("nonexistent-id") is None


def test_upsert_rsvp_going():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Marek", True)
    rsvps = database.get_rsvps(ev["id"])
    assert len(rsvps) == 1
    assert rsvps[0]["name"] == "Marek"
    assert rsvps[0]["going"] == 1


def test_upsert_rsvp_overwrites():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Marek", True)
    database.upsert_rsvp(ev["id"], "Marek", False)
    rsvps = database.get_rsvps(ev["id"])
    assert len(rsvps) == 1
    assert rsvps[0]["going"] == 0


def test_delete_event_valid_token():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Jano", True)
    ok = database.delete_event(ev["id"], ev["delete_token"])
    assert ok is True
    assert database.get_event(ev["id"]) is None
    assert database.get_rsvps(ev["id"]) == []


def test_delete_event_wrong_token():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    ok = database.delete_event(ev["id"], "wrong-token")
    assert ok is False
    assert database.get_event(ev["id"]) is not None


def test_get_all_events_split():
    database.create_event("Future Pub", "2099-12-31", "19:00", None)
    database.create_event("Past Pub", "2000-01-01", "19:00", None)
    upcoming, past = database.get_all_events()
    assert any(e["place"] == "Future Pub" for e in upcoming)
    assert any(e["place"] == "Past Pub" for e in past)


def test_get_all_events_going_names():
    database.create_event("Pub A", "2099-01-01", "18:00", None)
    result = database.create_event("Pub B", "2099-02-01", "19:00", None)
    event_id = result["id"]
    database.upsert_rsvp(event_id, "Jano", True)
    database.upsert_rsvp(event_id, "Ferko", True)
    database.upsert_rsvp(event_id, "Miro", False)
    upcoming, _ = database.get_all_events()
    pub_b = next(e for e in upcoming if e["place"] == "Pub B")
    assert pub_b["going_names"] == ["Jano", "Ferko"]


def test_get_all_events_going_names_empty():
    database.create_event("Pub C", "2099-03-01", "20:00", None)
    upcoming, _ = database.get_all_events()
    pub_c = next(e for e in upcoming if e["place"] == "Pub C")
    assert pub_c["going_names"] == []
