"""
Safety limits for a deployment that anyone with the link can reach, mainly to keep the Claude API bill in check.
Every limit is OFF unless its environment variable is set, so local runs and tests are never throttled:

  GENERATE_LIMIT_PER_HOUR   max generations per visitor per hour
  DAILY_GENERATION_LIMIT    max generations per day, across all visitors
  MAX_REQUIREMENT_CHARS     longest requirement text accepted

Counters live in memory, so they reset when the app restarts. Also set a monthly spend limit on the
API key itself in the Anthropic console: that is the limit that cannot be bypassed.
"""

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

_lock = threading.Lock()
_recent_by_ip = defaultdict(deque)
_daily = {"day": None, "count": 0}


def _int_setting(name: str) -> int:
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0


def client_ip(request) -> str:
    # Behind Render's proxy the last X-Forwarded-For entry is the address that reached the
    # proxy; earlier entries can be forged by the visitor.
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.remote_addr or "unknown"


def max_requirement_chars() -> int:
    return _int_setting("MAX_REQUIREMENT_CHARS")


def check_generation_allowed(ip: str, now: float = None):
    """Returns None if a generation may go ahead (and counts it), or a message saying why not."""
    hourly = _int_setting("GENERATE_LIMIT_PER_HOUR")
    daily = _int_setting("DAILY_GENERATION_LIMIT")
    now = time.time() if now is None else now
    today = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")

    with _lock:
        if _daily["day"] != today:
            _daily["day"], _daily["count"] = today, 0

        window = _recent_by_ip[ip]
        while window and now - window[0] > 3600:
            window.popleft()

        if daily > 0 and _daily["count"] >= daily:
            return "The daily generation limit has been reached - please try again tomorrow"
        if hourly > 0 and len(window) >= hourly:
            return f"You have reached the limit of {hourly} generations per hour - please try again later"

        window.append(now)
        _daily["count"] += 1
    return None


def reset() -> None:
    """Clears all counters (used by the tests)."""
    with _lock:
        _recent_by_ip.clear()
        _daily["day"], _daily["count"] = None, 0
