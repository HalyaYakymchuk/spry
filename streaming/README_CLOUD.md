# Payments Cloud Streaming Pipeline

Cloud-native event streaming and analytics pipeline deployed via AWS CloudFormation.

## Architecture

```
Producer (Python / boto3)
   │
   ▼
Kinesis Data Streams (payments-stream, on-demand)
   ├──► Firehose (payments-to-s3, 60s / 1MB buffer) ──► S3 (payments-stream/dt=YYYY-MM-DD/)
   │                                                        │
   │                                                        ▼
   │                                                  Glue Crawler (payments-stream-crawler)
   │                                                        │
   │                                                        ▼
   │                                                  Glue Catalog & Athena
   │
   └──► Lambda (payments-failure-check, BatchSize 100, Window 30s)
           │
           ▼ (Failure share > 10% and count >= 10)
        SNS Alerts (payments-failure-alerts -> Email)
```

## Files Created
- `infra/stream.yml`: CloudFormation template deploying Kinesis, Firehose, S3 delivery, Glue database & crawler, Lambda failure check, and SNS alerting topic.
- `streaming/cloud_producer.py`: Replays events sorted by `receivedAt` to Kinesis with deterministic `--fail-rate` injection, batched `put_records`, and retry handling.

## Producer Usage
```bash
# Standard replay (3000 events at 60 events/s)
python cloud_producer.py --limit 3000 --rate 60

# Replay with 30% injected failure rate for alert verification
python cloud_producer.py --limit 3000 --rate 60 --fail-rate 0.3
```
