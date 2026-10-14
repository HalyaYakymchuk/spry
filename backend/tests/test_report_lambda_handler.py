from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.reports.lambda_handler import detect_trigger, handler


def test_detect_trigger_sqs():
    event = {"Records": [{"eventSource": "aws:sqs", "body": "test"}]}
    assert detect_trigger(event) == "sqs"


def test_detect_trigger_schedule():
    assert detect_trigger({"source": "schedule"}) == "schedule"
    assert (
        detect_trigger({"detail": "event from aws.scheduler service"})
        == "schedule"
    )


def test_detect_trigger_s3():
    event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "s3": {"bucket": {"name": "b"}, "object": {"key": "k"}},
            }
        ]
    }
    assert detect_trigger(event) == "s3"


def test_detect_trigger_manual():
    assert detect_trigger({}) == "manual"
    assert detect_trigger({"some_key": "some_value"}) == "manual"
    assert detect_trigger(None) == "manual"


def test_handler_explicit_week(monkeypatch):
    mock_s3 = MagicMock()
    monkeypatch.setenv("REPORTS_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report",
        lambda week: b"Summary\nMetric\n",
    )

    result = handler(
        {"week": "2026-W40", "source": "schedule"}, s3_client=mock_s3
    )

    assert result == {
        "status": "ok",
        "week": "2026-W40",
        "key": "reports/2026-W40.csv",
    }
    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="reports/2026-W40.csv",
        Body=b"Summary\nMetric\n",
        ContentType="text/csv",
    )


def test_handler_default_week(monkeypatch):
    mock_s3 = MagicMock()
    monkeypatch.setenv("REPORTS_BUCKET_NAME", "my-reports-bucket")

    called_week = []

    def mock_build(w):
        called_week.append(w)
        return b"CSV data"

    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report", mock_build
    )

    result = handler({"source": "schedule"}, s3_client=mock_s3)

    expected_week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
        "%G-W%V"
    )
    assert called_week == [expected_week]
    assert result == {
        "status": "ok",
        "week": expected_week,
        "key": f"reports/{expected_week}.csv",
    }
    mock_s3.put_object.assert_called_once_with(
        Bucket="my-reports-bucket",
        Key=f"reports/{expected_week}.csv",
        Body=b"CSV data",
        ContentType="text/csv",
    )


def test_handler_logging(monkeypatch):
    mock_s3 = MagicMock()
    monkeypatch.setenv("REPORTS_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report",
        lambda week: b"data",
    )

    mock_log = MagicMock()
    monkeypatch.setattr("app.reports.lambda_handler.log", mock_log)

    handler({"week": "2026-W39"}, s3_client=mock_s3)

    mock_log.info.assert_called_once_with(
        "report-builder triggered: trigger=manual week=2026-W39"
    )


def test_handler_sqs_explicit_week(monkeypatch):
    import json

    mock_s3 = MagicMock()
    monkeypatch.setenv("REPORTS_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report",
        lambda week: b"sqs-data",
    )

    mock_log = MagicMock()
    monkeypatch.setattr("app.reports.lambda_handler.log", mock_log)

    sqs_event = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "body": json.dumps({"week": "2026-W39", "source": "manual"}),
            }
        ]
    }
    result = handler(sqs_event, s3_client=mock_s3)

    assert result == {
        "status": "ok",
        "week": "2026-W39",
        "key": "reports/2026-W39.csv",
    }
    mock_log.info.assert_called_once_with(
        "report-builder triggered: trigger=sqs week=2026-W39"
    )


def test_handler_sqs_schedule_null_week(monkeypatch):
    import json

    mock_s3 = MagicMock()
    monkeypatch.setenv("REPORTS_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report",
        lambda week: b"sqs-data",
    )

    mock_log = MagicMock()
    monkeypatch.setattr("app.reports.lambda_handler.log", mock_log)

    sqs_event = {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "body": json.dumps({"week": None, "source": "schedule"}),
            }
        ]
    }
    result = handler(sqs_event, s3_client=mock_s3)

    expected_week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
        "%G-W%V"
    )
    assert result == {
        "status": "ok",
        "week": expected_week,
        "key": f"reports/{expected_week}.csv",
    }
    mock_log.info.assert_called_once_with(
        f"report-builder triggered: trigger=sqs week={expected_week}"
    )


def test_handler_missing_bucket_raises(monkeypatch):
    monkeypatch.delenv("REPORTS_BUCKET_NAME", raising=False)
    monkeypatch.setattr(
        "app.reports.lambda_handler.build_weekly_report",
        lambda week: b"data",
    )

    with pytest.raises(ValueError, match="REPORTS_BUCKET_NAME"):
        handler({"week": "2026-W40"})
