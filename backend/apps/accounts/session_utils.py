"""CP5: pure helpers for turning an HTTP request into session metadata.

Deliberately free of any database access — everything here is a function of
its input arguments alone, which is what makes it possible to test this
module's logic without a live database (see
apps/accounts/tests/test_session_utils.py, which — unlike most of this
project's tests — actually runs and passes today; the same pattern CP4 used
for its access-code/challenge logic).

No new third-party dependency was added for user-agent parsing. This is a
deliberately lightweight, heuristic parser covering the mainstream browsers/
platforms well enough for a human-readable "which device is this?" session
list — it is NOT a comprehensive user-agent database (something like the
`user-agents` PyPI package would be, at the cost of an extra dependency this
checkpoint does not need). See BACKEND_LEARNING_GUIDE.md CP5 for the
trade-off this makes explicit.
"""
from .models import UserSession

UserSessionDeviceType = UserSession.DeviceType


def get_client_ip(request):
    """Best-effort client IP extraction, respecting a reverse proxy.

    `X-Forwarded-For` may contain a comma-separated chain
    (`client, proxy1, proxy2`); the first entry is the original client.
    Falls back to `REMOTE_ADDR` (the direct TCP peer) when no proxy header is
    present, which is correct for local development.
    """
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def parse_user_agent(user_agent_string):
    """Return (device_type, browser, operating_system) for a raw UA string.

    Order of checks matters: several browsers' user-agent strings contain
    other browsers' names for compatibility reasons (Edge and Opera both
    contain "Chrome/"; Chrome contains "Safari/"), so the more specific/
    spoofing browser must always be checked before the one it impersonates.
    """
    ua = (user_agent_string or "").strip()
    ua_lower = ua.lower()

    if not ua_lower:
        return (
            UserSessionDeviceType.UNKNOWN,
            "Unknown",
            "Unknown",
        )

    # --- device type ---
    if "ipad" in ua_lower or "tablet" in ua_lower:
        device_type = UserSessionDeviceType.TABLET
    elif "mobile" in ua_lower or "iphone" in ua_lower or ("android" in ua_lower and "mobi" in ua_lower):
        device_type = UserSessionDeviceType.MOBILE
    else:
        device_type = UserSessionDeviceType.DESKTOP

    # --- operating system ---
    # iPhone/iPad user agents contain the literal substring "like Mac OS X"
    # (e.g. "CPU iPhone OS 17_0 like Mac OS X") for legacy compatibility
    # reasons, so the iOS check MUST come before the macOS check — otherwise
    # every iPhone/iPad would be misreported as a Mac.
    if "windows" in ua_lower:
        operating_system = "Windows"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
        operating_system = "iOS"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        operating_system = "macOS"
    elif "android" in ua_lower:
        operating_system = "Android"
    elif "linux" in ua_lower:
        operating_system = "Linux"
    else:
        operating_system = "Unknown"

    # --- browser (order matters: check impersonating browsers first) ---
    if "edg/" in ua_lower or "edga/" in ua_lower or "edgios/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome/" in ua_lower or "crios/" in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower or "fxios/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower:
        browser = "Safari"
    else:
        browser = "Unknown"

    return device_type, browser, operating_system


def build_device_name(browser, operating_system):
    """A short, human-readable label for a session list — e.g. "Chrome on Windows"."""
    if browser == "Unknown" and operating_system == "Unknown":
        return "Unknown device"
    return f"{browser} on {operating_system}"
