# app/utils/scheduler_parser.py

import re
from typing import Optional

SLEEP_DURATION = 3  # seconds


class TimeConstants:
    A_HOUR = 3600
    A_DAY = 86400
    DAYS_30 = 30 * A_DAY


class TimeInterval:
    hourly = 'hourly'
    daily = 'daily'
    weekly = 'weekly'
    monthly = 'monthly'

    mapping = {
        hourly: TimeConstants.A_HOUR,
        daily: TimeConstants.A_DAY,
        weekly: 7 * TimeConstants.A_DAY,
        monthly: TimeConstants.DAYS_30
    }


SCHEDULER_REGEX = re.compile(r"""
    \^?(?P<run_now>[a-zA-Z0-9]*)?      # ^true
    @?(?P<interval>[a-zA-Z0-9]*)?      # @10
    /?(?P<delay>\d*)?                  # /5
    \$?(?P<end>\d*)?                   # $timestamp
    \#?(?P<retry>[a-zA-Z0-9]*)?        # #true
    """, re.VERBOSE, )


def to_bool(value: str, default=True) -> bool:
    if value is None or value == "":
        return default
    return value.lower() not in ["false", "0"]


def to_int(value: str, default=None) -> Optional[int]:
    if value is None or value == "":
        return default

    if value.isnumeric():
        return int(value)

    if value in TimeInterval.mapping:
        return TimeInterval.mapping[value]

    raise ValueError(f"Invalid interval: {value}")


def parse_scheduler(schedule: str):
    match = SCHEDULER_REGEX.fullmatch(schedule)

    if not match:
        raise ValueError(f"Invalid scheduler format: {schedule}")

    groups = match.groupdict()

    return {
        "run_now": to_bool(groups["run_now"], True),
        "interval": to_int(groups["interval"], None),
        "delay": to_int(groups["delay"], 0),
        "end_timestamp": to_int(groups["end"], None),
        "retry": to_bool(groups["retry"], True),
    }
