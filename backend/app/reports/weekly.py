import csv
import io
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.meeting import Meeting


def _parse_iso_week(week_str: str) -> tuple[int, int]:
    """Parse an ISO week string like '2026-W40' into (year, week_num)."""
    match = re.match(r"^(\d{4})-[wW](\d{1,2})$", week_str.strip())
    if not match:
        raise ValueError(
            f"Invalid ISO week format: '{week_str}'. Expected format like 'YYYY-Www' (e.g. '2026-W40')."
        )
    year = int(match.group(1))
    week_num = int(match.group(2))
    if week_num < 1 or week_num > 53:
        raise ValueError(
            f"Invalid week number: {week_num}. Week number must be between 1 and 53."
        )
    # Validate that the year actually has this week number
    try:
        date.fromisocalendar(year, week_num, 1)
    except ValueError as e:
        raise ValueError(f"Invalid ISO week '{week_str}': {e}") from e

    return year, week_num


def _to_utc(dt: datetime) -> datetime:
    """Ensure datetime is offset-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _meeting_duration_seconds(meeting: Meeting) -> float:
    """Calculate the meeting duration in seconds."""
    start = _to_utc(meeting.starts_at)
    end = _to_utc(meeting.ends_at)
    return max(0.0, (end - start).total_seconds())


def _generate_weekly_report(week: str, db: Session) -> bytes:
    year, week_num = _parse_iso_week(week)
    curr_week_str = f"{year}-W{week_num:02d}"

    # Current ISO week bounds (Monday 00:00:00 UTC to next Monday 00:00:00 UTC)
    curr_start_date = date.fromisocalendar(year, week_num, 1)
    curr_start_dt = datetime.combine(curr_start_date, time.min, tzinfo=timezone.utc)
    curr_end_dt = curr_start_dt + timedelta(days=7)

    # Previous ISO week bounds
    prev_start_dt = curr_start_dt - timedelta(days=7)
    prev_end_dt = curr_start_dt
    prev_iso_year, prev_iso_week, _ = prev_start_dt.date().isocalendar()
    prev_week_str = f"{prev_iso_year}-W{prev_iso_week:02d}"

    # Query current week meetings
    current_stmt = (
        select(Meeting)
        .where(Meeting.starts_at >= curr_start_dt, Meeting.starts_at < curr_end_dt)
        .order_by(Meeting.starts_at.asc())
    )
    current_meetings = list(db.scalars(current_stmt).all())
    # Extra check for databases where timezone handling may differ (e.g. SQLite naive timestamps)
    current_meetings = [
        m for m in current_meetings if curr_start_dt <= _to_utc(m.starts_at) < curr_end_dt
    ]

    # Query previous week meetings
    prev_stmt = (
        select(Meeting)
        .where(Meeting.starts_at >= prev_start_dt, Meeting.starts_at < prev_end_dt)
        .order_by(Meeting.starts_at.asc())
    )
    prev_meetings = list(db.scalars(prev_stmt).all())
    prev_meetings = [
        m for m in prev_meetings if prev_start_dt <= _to_utc(m.starts_at) < prev_end_dt
    ]

    # Metrics calculation
    current_count = len(current_meetings)
    current_total_secs = sum(_meeting_duration_seconds(m) for m in current_meetings)
    current_hours = current_total_secs / 3600.0

    prev_count = len(prev_meetings)
    prev_total_secs = sum(_meeting_duration_seconds(m) for m in prev_meetings)
    prev_hours = prev_total_secs / 3600.0

    delta_count = current_count - prev_count
    delta_hours = current_hours - prev_hours

    # Top 5 longest meetings sorted deterministically
    top_5_meetings = sorted(
        current_meetings,
        key=lambda m: (
            -_meeting_duration_seconds(m),
            _to_utc(m.starts_at),
            m.title,
            m.id if m.id is not None else 0,
        ),
    )[:5]

    # Build CSV output
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Summary Section
    writer.writerow(["Summary"])
    writer.writerow(
        [
            "Metric",
            f"Current Week ({curr_week_str})",
            f"Previous Week ({prev_week_str})",
            "Delta",
        ]
    )
    writer.writerow(
        [
            "Number of Meetings",
            current_count,
            prev_count,
            delta_count,
        ]
    )
    writer.writerow(
        [
            "Total Duration (hours)",
            round(current_hours, 2),
            round(prev_hours, 2),
            round(delta_hours, 2),
        ]
    )

    # Empty separator line
    writer.writerow([])

    # Top 5 Longest Meetings Section
    writer.writerow(["Top 5 Longest Meetings"])
    writer.writerow(["Title", "Starts At (UTC)", "Duration (mins)", "Attendee Count"])

    for m in top_5_meetings:
        starts_at_utc = _to_utc(m.starts_at)
        starts_at_str = (
            starts_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            if starts_at_utc.microsecond == 0
            else starts_at_utc.isoformat().replace("+00:00", "Z")
        )
        duration_mins = _meeting_duration_seconds(m) / 60.0
        duration_str = (
            str(int(duration_mins))
            if duration_mins.is_integer()
            else str(round(duration_mins, 2))
        )
        writer.writerow(
            [
                m.title,
                starts_at_str,
                duration_str,
                m.attendee_count,
            ]
        )

    return output.getvalue().encode("utf-8")


def build_weekly_report(week: str, db: Session | None = None) -> bytes:
    """Query the meetings of one ISO week (e.g. '2026-W40') and return the CSV as bytes."""
    if db is not None:
        return _generate_weekly_report(week, db)

    with SessionLocal() as session:
        return _generate_weekly_report(week, session)


if __name__ == "__main__":
    import sys

    arg_week = sys.argv[1] if len(sys.argv) > 1 else "2026-W40"
    report_bytes = build_weekly_report(arg_week)
    print(report_bytes.decode("utf-8"))
