def test_create_meeting(client):
    payload = {
        "title": "Quarterly Review",
        "starts_at": "2026-10-01T09:00:00Z",
        "ends_at": "2026-10-01T10:00:00Z",
        "attendee_count": 5,
    }
    response = client.post("/api/meetings", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["title"] == "Quarterly Review"
    assert data["starts_at"] == "2026-10-01T09:00:00Z"
    assert data["ends_at"] == "2026-10-01T10:00:00Z"
    assert data["attendee_count"] == 5


def test_list_meetings(client):
    client.post(
        "/api/meetings",
        json={
            "title": "Meeting A",
            "starts_at": "2026-10-01T09:00:00Z",
            "ends_at": "2026-10-01T10:00:00Z",
            "attendee_count": 3,
        },
    )
    client.post(
        "/api/meetings",
        json={
            "title": "Meeting B",
            "starts_at": "2026-10-01T11:00:00Z",
            "ends_at": "2026-10-01T12:00:00Z",
            "attendee_count": 8,
        },
    )

    response = client.get("/api/meetings")
    assert response.status_code == 200
    meetings = response.json()
    assert len(meetings) == 2
    assert meetings[0]["title"] == "Meeting A"
    assert meetings[1]["title"] == "Meeting B"


def test_validation_errors(client):
    # Invalid title: empty
    res = client.post(
        "/api/meetings",
        json={
            "title": "",
            "starts_at": "2026-10-01T09:00:00Z",
            "ends_at": "2026-10-01T10:00:00Z",
            "attendee_count": 2,
        },
    )
    assert res.status_code == 422

    # Invalid attendee count: 0
    res = client.post(
        "/api/meetings",
        json={
            "title": "Invalid Attendees",
            "starts_at": "2026-10-01T09:00:00Z",
            "ends_at": "2026-10-01T10:00:00Z",
            "attendee_count": 0,
        },
    )
    assert res.status_code == 422

    # Invalid ends_at before starts_at
    res = client.post(
        "/api/meetings",
        json={
            "title": "Invalid Timing",
            "starts_at": "2026-10-01T11:00:00Z",
            "ends_at": "2026-10-01T10:00:00Z",
            "attendee_count": 2,
        },
    )
    assert res.status_code == 422
