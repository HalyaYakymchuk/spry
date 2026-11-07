#!/usr/bin/env python3
"""Producer for payments event stream to AWS Kinesis.

Reads events from JSONL, sorts them by receivedAt, and replays them
to an Amazon Kinesis Data Stream in batches using put_records with key=invoiceId.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import boto3
from botocore.config import Config


def should_fail(invoice_id: str, fail_rate: float) -> bool:
    """Deterministically decide if an invoice should fail based on its md5 hash."""
    if fail_rate <= 0.0:
        return False
    h = int(hashlib.md5(invoice_id.encode("utf-8")).hexdigest()[:8], 16)
    return (h / 0xFFFFFFFF) < fail_rate


def locate_file(file_arg: str) -> str:
    """Resolve file path relative to current dir or script dir."""
    if os.path.exists(file_arg):
        return file_arg
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alt_path = os.path.join(script_dir, file_arg)
    if os.path.exists(alt_path):
        return alt_path
    repo_alt = os.path.join(script_dir, "..", file_arg)
    if os.path.exists(repo_alt):
        return repo_alt
    return file_arg


def main():
    parser = argparse.ArgumentParser(description="Replay payments events into AWS Kinesis.")
    parser.add_argument("--file", default="events.jsonl", help="Path to events.jsonl (default: events.jsonl)")
    parser.add_argument("--stream", default="payments-stream", help="Kinesis Data Stream name (default: payments-stream)")
    parser.add_argument("--region", default="eu-north-1", help="AWS region (default: eu-north-1)")
    parser.add_argument("--limit", type=int, default=3000, help="Maximum number of events to produce (default: 3000)")
    parser.add_argument("--rate", type=float, default=60.0, help="Replay rate in events/second (default: 60.0)")
    parser.add_argument("--fail-rate", type=float, default=0.0, help="Share of successful payments to fail (default: 0.0)")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of records per put_records batch (default: 50)")

    args = parser.parse_args()

    file_path = locate_file(args.file)
    if not os.path.exists(file_path):
        print(f"Error: file not found: {args.file} (checked {file_path})", file=sys.stderr)
        sys.exit(1)

    print(f"Loading events from {file_path}...")
    events = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # Sort events by receivedAt (processing time)
    events.sort(key=lambda e: e.get("receivedAt", ""))

    if args.limit is not None and args.limit > 0:
        events = events[: args.limit]

    total_events = len(events)
    print(
        f"Ready to produce {total_events} events to Kinesis stream '{args.stream}' "
        f"in region '{args.region}' at rate {args.rate} events/s (batch size: {args.batch_size})..."
    )

    client_config = Config(
        region_name=args.region,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    kinesis_client = boto3.client("kinesis", config=client_config)

    start_time = time.time()
    injected_failures = 0
    sent_count = 0
    total_retried_records = 0
    total_failed_records = 0
    batch_size = max(1, min(args.batch_size, 500))

    # Process events in batches
    for batch_start in range(0, total_events, batch_size):
        batch_events = events[batch_start : batch_start + batch_size]

        # Rate pacing based on the starting index of this batch
        if args.rate > 0:
            target_time = start_time + (batch_start / args.rate)
            delay = target_time - time.time()
            if delay > 0.001:
                time.sleep(delay)

        # Prepare records for Kinesis put_records
        records_to_send = []
        for ev in batch_events:
            invoice_id = str(ev.get("invoiceId", ""))

            # Deterministic failure injection
            if args.fail_rate > 0.0 and ev.get("status") == "success":
                if should_fail(invoice_id, args.fail_rate):
                    ev["status"] = "failure"
                    ev["failureReason"] = "Simulated failure via --fail-rate"
                    ev["finalAmount"] = 0
                    injected_failures += 1

            # Firehose concatenates records; Athena requires newline-delimited JSON
            record_data = (json.dumps(ev) + "\n").encode("utf-8")
            partition_key = invoice_id if invoice_id else "default"
            records_to_send.append(
                {
                    "Data": record_data,
                    "PartitionKey": partition_key,
                }
            )

        # Send batch and retry only rejected records
        current_records = records_to_send
        max_retries = 5
        retry_attempt = 0

        while current_records:
            try:
                response = kinesis_client.put_records(
                    StreamName=args.stream,
                    Records=current_records,
                )
            except Exception as e:
                print(f"\nERROR: put_records request failed: {e}", file=sys.stderr)
                total_failed_records += len(current_records)
                break

            failed_count = response.get("FailedRecordCount", 0)
            if failed_count == 0:
                break

            retry_attempt += 1
            total_retried_records += failed_count
            if retry_attempt > max_retries:
                print(
                    f"\nWarning: Reached max retries ({max_retries}) for {failed_count} rejected records",
                    file=sys.stderr,
                )
                total_failed_records += failed_count
                break

            # Filter only records that were rejected by Kinesis
            resp_records = response.get("Records", [])
            current_records = [
                rec
                for rec, resp in zip(current_records, resp_records)
                if resp.get("ErrorCode") is not None
            ]
            time.sleep(0.1 * (2 ** (retry_attempt - 1)))

        sent_count += len(batch_events)

        if sent_count % 500 == 0 or sent_count == total_events:
            elapsed = time.time() - start_time
            curr_rate = sent_count / elapsed if elapsed > 0 else 0
            print(f"Produced {sent_count}/{total_events} events ({curr_rate:.1f} events/s)...")

    total_time = time.time() - start_time
    actual_rate = total_events / total_time if total_time > 0 else 0

    print("\n" + "=" * 50)
    print("Production Summary")
    print("=" * 50)
    print(f"Total events processed: {total_events}")
    print(f"Successfully produced:  {sent_count - total_failed_records}")
    print(f"Injected failures:      {injected_failures}")
    print(f"Rejected records:       {total_failed_records}")
    print(f"Retried records:        {total_retried_records}")
    print(f"Total time:             {total_time:.2f} s")
    print(f"Average throughput:     {actual_rate:.1f} events/s")
    print(f"Target stream:          {args.stream} ({args.region})")
    print("=" * 50)


if __name__ == "__main__":
    main()
