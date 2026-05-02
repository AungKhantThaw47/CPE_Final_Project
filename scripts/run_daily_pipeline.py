#!/usr/bin/env python3
import re
import subprocess
import sys
from datetime import datetime, timedelta

DATE_FMT = "%d-%m-%Y"
DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")


def parse_date(value: str) -> datetime:
    if not DATE_RE.match(value):
        raise ValueError(f"Date '{value}' does not match DD-MM-YYYY format")
    return datetime.strptime(value, DATE_FMT)


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "Usage: python3 run_daily_pipeline.py START_DATE END_DATE COMMAND_TEMPLATE\n"
            "\n"
            "Arguments:\n"
            "  START_DATE   - Start date in DD-MM-YYYY format (e.g., 20-03-2026)\n"
            "  END_DATE     - End date in DD-MM-YYYY format (e.g., 22-03-2026)\n"
            "  COMMAND      - Command template with {DATE} placeholder (quoted)\n",
            file=sys.stderr,
        )
        return 1

    start_date = parse_date(sys.argv[1])
    end_date = parse_date(sys.argv[2])
    command_template = sys.argv[3]

    if end_date < start_date:
        log("ERROR: END_DATE must be on or after START_DATE")
        return 1

    log("Starting date-range command spawner")
    log(f"  Date range:   {start_date.strftime(DATE_FMT)} to {end_date.strftime(DATE_FMT)}")
    log("  Mode:         fire-and-forget (no waiting)")
    log(f"  Command:      {command_template}")
    log("")

    current = start_date
    while current <= end_date:
        current_date = current.strftime(DATE_FMT)
        cmd = command_template.replace("{DATE}", current_date)

        log(f"Spawning: {cmd}")
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        current += timedelta(days=1)

    log("All commands spawned!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())