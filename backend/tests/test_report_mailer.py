from unittest.mock import MagicMock

import pytest

from app.reports.mailer import handler


def test_mailer_skips_empty_or_malformed_event():
    assert handler({}) == {"status": "skipped"}
    assert handler(None) == {"status": "skipped"}
    assert handler({"Records": []}) == {"status": "skipped"}
    assert handler({"Records": [{"not_s3": {}}]}) == {"status": "skipped"}


def test_mailer_skips_non_report_keys():
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "other/file.txt"},
                }
            }
        ]
    }
    assert handler(event) == {"status": "skipped"}

    event_wrong_ext = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "reports/summary.json"},
                }
            }
        ]
    }
    assert handler(event_wrong_ext) == {"status": "skipped"}


def test_mailer_processes_valid_report(monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@example.com")

    mock_s3 = MagicMock()
    mock_ses = MagicMock()

    mock_body = MagicMock()
    mock_body.read.return_value = b"metric,value\nmeetings,5\n"
    mock_s3.get_object.return_value = {"Body": mock_body}

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "peach-reports-bucket"},
                    "object": {"key": "reports/2026-W38.csv"},
                }
            }
        ]
    }

    result = handler(event, s3_client=mock_s3, ses_client=mock_ses)

    assert result == {
        "status": "sent",
        "recipient": "recipient@example.com",
        "file": "2026-W38.csv",
    }

    mock_s3.get_object.assert_called_once_with(
        Bucket="peach-reports-bucket",
        Key="reports/2026-W38.csv",
    )

    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["FromEmailAddress"] == "sender@example.com"
    assert call_kwargs["Destination"] == {"ToAddresses": ["recipient@example.com"]}
    assert b"2026-W38.csv" in call_kwargs["Content"]["Raw"]["Data"]
    assert b"Weekly Insights Report: 2026-W38.csv" in call_kwargs["Content"]["Raw"]["Data"]


def test_mailer_fallback_recipient(monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "sender@example.com")
    monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)

    mock_s3 = MagicMock()
    mock_ses = MagicMock()

    mock_body = MagicMock()
    mock_body.read.return_value = b"csv-data"
    mock_s3.get_object.return_value = {"Body": mock_body}

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "peach-reports-bucket"},
                    "object": {"key": "reports/2026-W39.csv"},
                }
            }
        ]
    }

    result = handler(event, s3_client=mock_s3, ses_client=mock_ses)
    assert result["status"] == "sent"
    assert result["recipient"] == "sender@example.com"

    call_kwargs = mock_ses.send_email.call_args.kwargs
    assert call_kwargs["Destination"] == {"ToAddresses": ["sender@example.com"]}
