#!/usr/bin/env python3
"""Spawn per-day dvb-coordinator-job executions for a date range.

Usage:
  python3 run_daily_pipeline.py START_DATE END_DATE [COMMAND_TEMPLATE]

When COMMAND_TEMPLATE is omitted the script triggers the dvb-coordinator-job
Cloud Run Job for each day using a subprocess arg-list (no shell quoting
issues).  Pass an explicit COMMAND_TEMPLATE containing a {DATE} placeholder
to override with a custom shell command instead.
"""
import re
import subprocess
import sys
from datetime import datetime, timedelta

DATE_FMT = "%d-%m-%Y"
DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")

COORDINATOR_JOB_NAME = "dvb-coordinator-job"
JOB_REGION = "asia-southeast1"


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")


def parse_date(value: str) -> datetime:
    if not DATE_RE.match(value):
        raise ValueError(f"Date '{value}' does not match DD-MM-YYYY format")
    return datetime.strptime(value, DATE_FMT)


def spawn_coordinator(start_str: str, end_str: str) -> None:
    subprocess.Popen(
        [
            "gcloud", "run", "jobs", "execute", COORDINATOR_JOB_NAME,
            f"--region={JOB_REGION}",
            "--format=none",
            f"--update-env-vars=CRAWL_START_DATE={start_str},CRAWL_END_DATE={end_str}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def spawn_custom(command_template: str, date_str: str) -> None:
    cmd = command_template.replace("{DATE}", date_str)
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: python3 run_daily_pipeline.py START_DATE END_DATE [COMMAND_TEMPLATE]\n"
            "\n"
            "Arguments:\n"
            "  START_DATE        Start date in DD-MM-YYYY format (e.g., 01-04-2025)\n"
            "  END_DATE          End date   in DD-MM-YYYY format (e.g., 30-04-2025)\n"
            "  COMMAND_TEMPLATE  Optional shell command with {DATE} placeholder.\n"
            "                    Omit to trigger dvb-coordinator-job per day.\n",
            file=sys.stderr,
        )
        return 1

    start_date = parse_date(sys.argv[1])
    end_date = parse_date(sys.argv[2])
    command_template = sys.argv[3] if len(sys.argv) > 3 else None

    if end_date < start_date:
        log("ERROR: END_DATE must be on or after START_DATE")
        return 1

    start_str = start_date.strftime(DATE_FMT)
    end_str = end_date.strftime(DATE_FMT)

    log(f"Date range:  {start_str} to {end_str}")
    log("Mode:        fire-and-forget (no waiting)")

    if command_template:
        log(f"Execution:   custom shell command (per-day loop)")
        log(f"Command:     {command_template}")
        log("")
        current = start_date
        while current <= end_date:
            current_date = current.strftime(DATE_FMT)
            log(f"Spawning: {current_date}")
            spawn_custom(command_template, current_date)
            current += timedelta(days=1)
        log("All commands spawned!")
    else:
        log(f"Execution:   coordinator job  ({COORDINATOR_JOB_NAME} @ {JOB_REGION})")
        log("")
        log(f"Spawning coordinator for {start_str} to {end_str} ...")
        spawn_coordinator(start_str, end_str)
        log("Coordinator spawned — it will discover all links and fan out crawler sub-jobs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
