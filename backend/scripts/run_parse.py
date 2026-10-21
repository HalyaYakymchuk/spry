"""Local CLI test runner for agenda parsing using Amazon Bedrock Anthropic Claude."""

import argparse
from datetime import date
import os
import sys

# Ensure UTF-8 output on Windows / MSYS2 terminals to support emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.ai.agenda import AgendaParseError, parse_agenda


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse raw meeting agenda text into structured JSON."
    )
    parser.add_argument(
        "positional_text",
        nargs="?",
        default=None,
        help="Raw meeting agenda text to parse.",
    )
    parser.add_argument(
        "--text",
        "-t",
        default=None,
        help="Raw meeting agenda text (alternative to positional argument).",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Reference date in YYYY-MM-DD format (defaults to current date).",
    )
    parser.add_argument(
        "--tz",
        default="Europe/Kyiv",
        help="Timezone for resolving dates/times (defaults to Europe/Kyiv).",
    )

    args = parser.parse_args()

    raw_text = args.text or args.positional_text or os.getenv("TEXT")
    if not raw_text or not raw_text.strip():
        print(
            "Error: No text provided. Pass text as an argument, via --text, or set TEXT env var.",
            file=sys.stderr,
        )
        return 1

    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError as err:
            print(f"Error: Invalid date format for --today: {err}", file=sys.stderr)
            return 1
    else:
        today = date.today()

    tz = args.tz

    try:
        parsed, usage = parse_agenda(text=raw_text, today=today, tz=tz)
        print(parsed.model_dump_json(indent=2))
        print(
            f"\nUsage: input_tokens={usage.get('input_tokens', 0)}, "
            f"output_tokens={usage.get('output_tokens', 0)}"
        )
        return 0
    except AgendaParseError as err:
        print(f"Error parsing agenda: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
