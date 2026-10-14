import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3

from app.reports.weekly import build_weekly_report

log = logging.getLogger(__name__)
if not log.handlers and not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
else:
    log.setLevel(logging.INFO)

logger = log


def detect_trigger(event: Any) -> str:
    """Detect the trigger source of the invocation event.

    Recognized triggers:
    - 'sqs': if 'Records' in event and first record contains 'body' or eventSource is 'aws:sqs'
    - 'schedule': if event.get('source') == 'schedule' or 'aws.scheduler' in str(event)
    - 's3': if 'Records' in event and first record eventSource is 'aws:s3'
    - 'manual': fallback default
    """
    if not isinstance(event, dict):
        return "manual"

    records = event.get("Records")
    if (
        isinstance(records, list)
        and len(records) > 0
        and isinstance(records[0], dict)
    ):
        if "body" in records[0] or records[0].get("eventSource") == "aws:sqs":
            return "sqs"
        if records[0].get("eventSource") == "aws:s3":
            return "s3"

    if event.get("source") == "schedule" or "aws.scheduler" in str(event):
        return "schedule"

    return "manual"


def handler(
    event: dict[str, Any] | None = None,
    context: Any = None,
    s3_client: Any = None,
) -> dict[str, Any]:
    """Lambda entry point for weekly report builder."""
    event = event or {}

    records = event.get("Records") if isinstance(event, dict) else None
    if (
        isinstance(records, list)
        and len(records) > 0
        and isinstance(records[0], dict)
        and "body" in records[0]
    ):
        trigger = "sqs"
        raw_body = records[0]["body"]
        payload = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
        if not isinstance(payload, dict):
            payload = {}
    else:
        payload = event if isinstance(event, dict) else {}
        if payload.get("source") == "schedule" or "aws.scheduler" in str(event):
            trigger = "schedule"
        else:
            trigger = "manual"

    raw_week = payload.get("week")
    if raw_week is not None and str(raw_week).strip():
        week = str(raw_week).strip()
    else:
        prev_week_dt = datetime.now(timezone.utc) - timedelta(days=7)
        week = prev_week_dt.strftime("%G-W%V")

    log.info(f"report-builder triggered: trigger={trigger} week={week}")

    report_bytes = build_weekly_report(week)

    bucket = os.environ.get("REPORTS_BUCKET_NAME")
    if not bucket:
        raise ValueError("Environment variable REPORTS_BUCKET_NAME is not set")

    key = f"reports/{week}.csv"
    client = s3_client or boto3.client("s3")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=report_bytes,
        ContentType="text/csv",
    )

    return {
        "status": "ok",
        "week": week,
        "key": key,
    }
