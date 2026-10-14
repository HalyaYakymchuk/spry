import json
import logging
import os
import urllib.parse
from email.message import EmailMessage
from typing import Any

import boto3

log = logging.getLogger(__name__)


def handler(
    event: dict[str, Any] | None = None,
    context: Any = None,
    s3_client: Any = None,
    ses_client: Any = None,
) -> dict[str, Any]:
    """Lambda entry point for weekly report mailer.

    Triggered by S3 ObjectCreated events when a report is uploaded to reports/*.csv.
    Sends the CSV report as an email attachment via Amazon SES v2.
    """
    event = event or {}
    print("report-mailer triggered:", json.dumps(event))

    records = event.get("Records")
    if not isinstance(records, list) or not records:
        print("Skipping event with no records")
        return {"status": "skipped"}

    record = records[0].get("s3")
    if not isinstance(record, dict):
        print("Skipping record without S3 payload")
        return {"status": "skipped"}

    bucket = record["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["object"]["key"])

    # Extra safeguard: ensure key starts with reports/ and ends with .csv
    if not (key.startswith("reports/") and key.endswith(".csv")):
        print(f"Skipping non-report key: {key}")
        return {"status": "skipped"}

    s3 = s3_client or boto3.client("s3")
    ses = ses_client or boto3.client("sesv2")

    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    csv_data = body.read() if hasattr(body, "read") else body

    filename = os.path.basename(key)
    sender = os.environ.get("SENDER_EMAIL") or "reports@spry.org.ua"
    recipient = os.environ.get("RECIPIENT_EMAIL") or sender

    msg = EmailMessage()
    msg["Subject"] = f"Weekly Insights Report: {filename}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"Hello,\n\nPlease find attached the weekly report for {filename}.\n\nBest regards,\nSpry Team"
    )
    msg.add_attachment(csv_data, maintype="text", subtype="csv", filename=filename)

    ses.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": [recipient]},
        Content={"Raw": {"Data": msg.as_bytes()}},
    )
    print(f"Successfully sent {filename} to {recipient}")
    return {"status": "sent", "recipient": recipient, "file": filename}
