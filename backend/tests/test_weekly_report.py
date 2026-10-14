import csv
import io
from datetime import datetime, timezone

import pytest

from app.models.meeting import Meeting
from app.reports.weekly import build_weekly_report


def test_build_weekly_report_structure_and_metrics(db_session, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    test_sessionmaker = sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind()
    )
    monkeypatch.setattr("app.reports.weekly.SessionLocal", test_sessionmaker)

    # Week 40 of 2026 runs from Monday 2026-09-28 00:00:00 UTC to Monday 2026-10-05 00:00:00 UTC.
    # Week 39 runs from Monday 2026-09-21 00:00:00 UTC to Monday 2026-09-28 00:00:00 UTC.
    # Week 41 runs from Monday 2026-10-05 00:00:00 UTC to Monday 2026-10-12 00:00:00 UTC.

    # 1. Previous week meetings (Week 39)
    m_prev1 = Meeting(
        title="W39 Retrospective",
        starts_at=datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc),  # 60 mins (1.0 hr)
        attendee_count=4,
    )
    m_prev2 = Meeting(
        title="W39 1-on-1",
        starts_at=datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc),  # 90 mins (1.5 hrs)
        attendee_count=2,
    )

    # 2. Current week meetings (Week 40)
    # Total 6 meetings to test top 5 cutoff
    m_curr1 = Meeting(
        title="Weekly Standup Monday",
        starts_at=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc),  # 30 mins
        attendee_count=6,
    )
    m_curr2 = Meeting(
        title="Architecture Deep Dive",
        starts_at=datetime(2026, 9, 29, 13, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 29, 16, 0, tzinfo=timezone.utc),  # 180 mins
        attendee_count=8,
    )
    m_curr3 = Meeting(
        title="Product Roadmap",
        starts_at=datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),  # 120 mins
        attendee_count=12,
    )
    m_curr4 = Meeting(
        title="Sprint Planning",
        starts_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 1, 10, 30, tzinfo=timezone.utc),  # 90 mins
        attendee_count=7,
    )
    m_curr5 = Meeting(
        title="Engineering All Hands",
        starts_at=datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc),  # 60 mins
        attendee_count=25,
    )
    m_curr6 = Meeting(
        title="Quick Sync (Shortest)",
        starts_at=datetime(2026, 10, 2, 16, 30, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 2, 16, 45, tzinfo=timezone.utc),  # 15 mins (should NOT be in top 5)
        attendee_count=3,
    )

    # 3. Next week meeting (Week 41 - should be excluded)
    m_next = Meeting(
        title="W41 Future Planning",
        starts_at=datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),
        attendee_count=5,
    )

    db_session.add_all([
        m_prev1,
        m_prev2,
        m_curr1,
        m_curr2,
        m_curr3,
        m_curr4,
        m_curr5,
        m_curr6,
        m_next,
    ])
    db_session.commit()

    # Call with strictly one parameter (using monkeypatched SessionLocal)
    report_bytes = build_weekly_report("2026-W40")
    assert isinstance(report_bytes, bytes)

    # Check UTF-8 decoding
    content = report_bytes.decode("utf-8")
    assert "Summary" in content
    assert "Top 5 Longest Meetings" in content

    # Parse with csv.reader
    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if r]

    # Check Summary Header
    assert rows[0] == ["Summary"]
    assert rows[1] == [
        "Metric",
        "Current Week (2026-W40)",
        "Previous Week (2026-W39)",
        "Delta",
    ]

    # Metrics verification:
    # Current week meetings: 6
    # Current week durations: 30 + 180 + 120 + 90 + 60 + 15 = 495 mins = 8.25 hours
    # Previous week meetings: 2
    # Previous week durations: 60 + 90 = 150 mins = 2.50 hours
    # Deltas: count = 6 - 2 = 4, duration = 8.25 - 2.5 = 5.75 hours
    assert rows[2] == ["Number of Meetings", "6", "2", "4"]
    assert rows[3] == ["Total Duration (hours)", "8.25", "2.5", "5.75"]

    # Top 5 Section Header
    assert rows[4] == ["Top 5 Longest Meetings"]
    assert rows[5] == ["Title", "Starts At (UTC)", "Duration (mins)", "Attendee Count"]

    # 5 longest meetings should be:
    # 1. Architecture Deep Dive (180 mins)
    # 2. Product Roadmap (120 mins)
    # 3. Sprint Planning (90 mins)
    # 4. Engineering All Hands (60 mins)
    # 5. Weekly Standup Monday (30 mins)
    # "Quick Sync (Shortest)" (15 mins) should be excluded
    meeting_rows = rows[6:]
    assert len(meeting_rows) == 5

    assert meeting_rows[0][0] == "Architecture Deep Dive"
    assert meeting_rows[0][1] == "2026-09-29T13:00:00Z"
    assert meeting_rows[0][2] == "180"
    assert meeting_rows[0][3] == "8"

    assert meeting_rows[1][0] == "Product Roadmap"
    assert meeting_rows[1][1] == "2026-09-30T10:00:00Z"
    assert meeting_rows[1][2] == "120"
    assert meeting_rows[1][3] == "12"

    assert meeting_rows[2][0] == "Sprint Planning"
    assert meeting_rows[2][1] == "2026-10-01T09:00:00Z"
    assert meeting_rows[2][2] == "90"
    assert meeting_rows[2][3] == "7"

    assert meeting_rows[3][0] == "Engineering All Hands"
    assert meeting_rows[3][1] == "2026-10-02T15:00:00Z"
    assert meeting_rows[3][2] == "60"
    assert meeting_rows[3][3] == "25"

    assert meeting_rows[4][0] == "Weekly Standup Monday"
    assert meeting_rows[4][1] == "2026-09-28T09:00:00Z"
    assert meeting_rows[4][2] == "30"
    assert meeting_rows[4][3] == "6"


def test_build_weekly_report_empty_week(db_session):
    # Calling report for a week with no meetings in either week
    report_bytes = build_weekly_report("2026-W10", db=db_session)
    content = report_bytes.decode("utf-8")

    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if r]

    assert rows[0] == ["Summary"]
    assert rows[2] == ["Number of Meetings", "0", "0", "0"]
    assert rows[3] == ["Total Duration (hours)", "0.0", "0.0", "0.0"]
    assert rows[4] == ["Top 5 Longest Meetings"]
    assert rows[5] == ["Title", "Starts At (UTC)", "Duration (mins)", "Attendee Count"]
    assert len(rows) == 6  # No meeting data rows


def test_build_weekly_report_idempotent(db_session):
    # Add a meeting
    db_session.add(
        Meeting(
            title="Idempotency Test Meeting",
            starts_at=datetime(2026, 9, 28, 11, 0, tzinfo=timezone.utc),
            ends_at=datetime(2026, 9, 28, 12, 15, tzinfo=timezone.utc),  # 75 mins
            attendee_count=3,
        )
    )
    db_session.commit()

    first_run = build_weekly_report("2026-W40", db=db_session)
    second_run = build_weekly_report("2026-W40", db=db_session)
    third_run = build_weekly_report("2026-W40", db=db_session)

    assert first_run == second_run == third_run


def test_build_weekly_report_invalid_week_inputs(db_session):
    with pytest.raises(ValueError, match="Invalid ISO week format"):
        build_weekly_report("2026-40", db=db_session)

    with pytest.raises(ValueError, match="Invalid ISO week format"):
        build_weekly_report("last-week", db=db_session)

    with pytest.raises(ValueError, match="between 1 and 53"):
        build_weekly_report("2026-W00", db=db_session)

    with pytest.raises(ValueError, match="between 1 and 53"):
        build_weekly_report("2026-W54", db=db_session)

    # 2025 has only 52 weeks
    with pytest.raises(ValueError, match="Invalid ISO week"):
        build_weekly_report("2025-W53", db=db_session)


def test_build_weekly_report_iso_year_boundary(db_session):
    # Week 1 of 2026 starts Monday 2025-12-29 00:00:00 UTC.
    # Previous week is Week 52 of 2025 (Monday 2025-12-22 00:00:00 UTC).
    m_prev = Meeting(
        title="EndOfYear Review",
        starts_at=datetime(2025, 12, 23, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2025, 12, 23, 11, 0, tzinfo=timezone.utc),
        attendee_count=5,
    )
    m_curr = Meeting(
        title="NewYear Kickoff",
        starts_at=datetime(2025, 12, 29, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2025, 12, 29, 10, 30, tzinfo=timezone.utc),  # 90 mins = 1.5 hrs
        attendee_count=10,
    )
    db_session.add_all([m_prev, m_curr])
    db_session.commit()

    report_bytes = build_weekly_report("2026-W01", db=db_session)
    content = report_bytes.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if r]

    # Check header has 2026-W01 and 2025-W52
    assert rows[1] == [
        "Metric",
        "Current Week (2026-W01)",
        "Previous Week (2025-W52)",
        "Delta",
    ]
    assert rows[2] == ["Number of Meetings", "1", "1", "0"]
    assert rows[3] == ["Total Duration (hours)", "1.5", "1.0", "0.5"]


def test_boundary_timestamps_and_sorting(db_session):
    # Monday 2026-09-28 00:00:00 UTC (exact start of week 40)
    m_start = Meeting(
        title="Start of Week Meeting",
        starts_at=datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 28, 1, 0, 0, tzinfo=timezone.utc),
        attendee_count=2,
    )
    # Sunday 2026-10-04 23:59:59 UTC (still inside week 40)
    m_end_inside = Meeting(
        title="End of Week Meeting",
        starts_at=datetime(2026, 10, 4, 23, 0, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 4, 23, 45, 0, tzinfo=timezone.utc),
        attendee_count=3,
    )
    # Monday 2026-10-05 00:00:00 UTC (exact start of week 41 - should be excluded)
    m_next_boundary = Meeting(
        title="Next Week Exact Start",
        starts_at=datetime(2026, 10, 5, 0, 0, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 5, 1, 0, 0, tzinfo=timezone.utc),
        attendee_count=4,
    )
    db_session.add_all([m_start, m_end_inside, m_next_boundary])
    db_session.commit()

    report_bytes = build_weekly_report("2026-W40", db=db_session)
    content = report_bytes.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if r]

    # Current week should have exactly 2 meetings
    assert rows[2] == ["Number of Meetings", "2", "0", "2"]
    titles = [r[0] for r in rows[6:]]
    assert "Start of Week Meeting" in titles
    assert "End of Week Meeting" in titles
    assert "Next Week Exact Start" not in titles

