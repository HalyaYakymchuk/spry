from fastapi import status


def test_create_meeting_and_save_agenda_with_ai_metadata(client):
    # 1. Create a meeting
    meeting_resp = client.post(
        "/api/meetings",
        json={
            "title": "Sprint Planning Q4",
            "starts_at": "2026-10-22T10:00:00Z",
            "ends_at": "2026-10-22T11:00:00Z",
            "attendee_count": 6,
        },
    )
    assert meeting_resp.status_code == status.HTTP_201_CREATED
    meeting_id = meeting_resp.json()["id"]

    # 2. Raw suggested agenda returned by the parser
    ai_raw_suggestion = {
        "title": "Sprint Planning Q4",
        "starts_at": "2026-10-22T10:00:00",
        "duration_minutes": 60,
        "items": [
            {"topic": "Review roadmap", "owner": "Alice", "minutes": 20},
            {"topic": "Capacity review", "owner": "Bob", "minutes": 40},
        ],
        "action_items": [
            {"task": "Prepare sprint board", "owner": "Charlie", "due": "2026-10-23"}
        ],
        "language": "en",
    }

    # User slightly corrects the first topic title: "Review product roadmap"
    agenda_payload = {
        "title": "Sprint Planning Q4 - Refined",
        "items": [
            {"topic": "Review product roadmap", "owner": "Alice", "minutes": 25},
            {"topic": "Capacity review", "owner": "Bob", "minutes": 35},
        ],
        "action_items": [
            {"task": "Prepare sprint board", "owner": "Charlie", "due": "2026-10-23"}
        ],
        "ai_suggestion": ai_raw_suggestion,
        "model": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
    }

    save_resp = client.post(f"/api/meetings/{meeting_id}/agenda", json=agenda_payload)
    assert save_resp.status_code == status.HTTP_201_CREATED
    data = save_resp.json()

    assert data["meeting_id"] == meeting_id
    assert data["title"] == "Sprint Planning Q4 - Refined"
    assert len(data["items"]) == 2
    assert data["items"][0]["topic"] == "Review product roadmap"
    assert data["items"][0]["minutes"] == 25
    assert len(data["action_items"]) == 1
    assert data["action_items"][0]["owner"] == "Charlie"
    # Ensure AI quality tracking signals are preserved
    assert data["ai_suggestion"] == ai_raw_suggestion
    assert data["model"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert data["prompt_version"] == "agenda-v1"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_update_existing_agenda(client):
    # 1. Create meeting
    m_resp = client.post(
        "/api/meetings",
        json={
            "title": "Standup",
            "starts_at": "2026-10-22T09:00:00Z",
            "ends_at": "2026-10-22T09:15:00Z",
            "attendee_count": 4,
        },
    )
    meeting_id = m_resp.json()["id"]

    # 2. Initial save
    ai_raw = {"title": "Daily Standup", "items": [{"topic": "Blockers", "owner": None, "minutes": 15}]}
    payload_1 = {
        "title": "Daily Standup",
        "items": [{"topic": "Blockers", "owner": None, "minutes": 15}],
        "action_items": [],
        "ai_suggestion": ai_raw,
        "model": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
    }
    r1 = client.post(f"/api/meetings/{meeting_id}/agenda", json=payload_1)
    assert r1.status_code == status.HTTP_201_CREATED
    agenda_id = r1.json()["id"]

    # 3. Update existing agenda (should return 200 OK and keep same agenda id)
    payload_2 = {
        "title": "Daily Standup - Updated",
        "items": [
            {"topic": "Blockers", "owner": "Dave", "minutes": 10},
            {"topic": "Announcements", "owner": "Eve", "minutes": 5},
        ],
        "action_items": [{"task": "Unblock database access", "owner": "Dave", "due": "2026-10-22"}],
        "ai_suggestion": ai_raw,
        "model": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_version": "agenda-v1",
    }
    r2 = client.post(f"/api/meetings/{meeting_id}/agenda", json=payload_2)
    assert r2.status_code == status.HTTP_200_OK
    data2 = r2.json()
    assert data2["id"] == agenda_id
    assert data2["title"] == "Daily Standup - Updated"
    assert len(data2["items"]) == 2
    assert len(data2["action_items"]) == 1
    assert data2["ai_suggestion"] == ai_raw


def test_get_meeting_agenda(client):
    m_resp = client.post(
        "/api/meetings",
        json={
            "title": "Retro",
            "starts_at": "2026-10-22T14:00:00Z",
            "ends_at": "2026-10-22T15:00:00Z",
            "attendee_count": 5,
        },
    )
    meeting_id = m_resp.json()["id"]

    # Before agenda is created, returns 200 with None (or 404)
    get_before = client.get(f"/api/meetings/{meeting_id}/agenda")
    assert get_before.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND)
    if get_before.status_code == status.HTTP_200_OK:
        assert get_before.json() is None

    # Save agenda
    client.post(
        f"/api/meetings/{meeting_id}/agenda",
        json={
            "title": "Sprint Retro",
            "items": [{"topic": "What went well", "owner": "All", "minutes": 30}],
            "action_items": [],
            "ai_suggestion": None,
            "model": None,
            "prompt_version": None,
        },
    )

    # 200 after agenda is created
    get_after = client.get(f"/api/meetings/{meeting_id}/agenda")
    assert get_after.status_code == status.HTTP_200_OK
    assert get_after.json()["title"] == "Sprint Retro"
    assert get_after.json()["ai_suggestion"] is None

    # Also check /meetings/{id} embeds agenda
    get_meeting = client.get(f"/api/meetings/{meeting_id}")
    assert get_meeting.status_code == status.HTTP_200_OK
    meeting_data = get_meeting.json()
    assert meeting_data["agenda"] is not None
    assert meeting_data["agenda"]["title"] == "Sprint Retro"


def test_agenda_nonexistent_meeting_404(client):
    res = client.post(
        "/api/meetings/999999/agenda",
        json={"title": "Test", "items": [], "action_items": []},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND

    res_get = client.get("/api/meetings/999999/agenda")
    assert res_get.status_code == status.HTTP_404_NOT_FOUND
