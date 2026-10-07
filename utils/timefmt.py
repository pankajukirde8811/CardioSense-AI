"""Turn the UTC times stored in the database into the user's local time."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = os.environ.get("APP_TIMEZONE", "Europe/Berlin")


def get_zone(name=None):
    """Return a valid timezone, falling back to the app default."""
    for candidate in (name, DEFAULT_TIMEZONE, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return timezone.utc


def is_valid_zone(name):
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False


def to_local(utc_text, zone_name=None):
    """'2026-10-07 03:25:41' (UTC, from SQLite) -> aware local datetime."""
    moment = datetime.strptime(utc_text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return moment.astimezone(get_zone(zone_name))


def now_local(zone_name=None):
    return datetime.now(timezone.utc).astimezone(get_zone(zone_name))


def format_dt(moment):
    """-> '07 Oct 2026, 05:25 CEST'"""
    return f"{moment.strftime('%d %b %Y, %H:%M')} {moment.tzname()}"
