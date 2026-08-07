"""CP5: tests for apps/accounts/session_utils.py.

Deliberately written to need NO database connection — same pattern CP4
established for its access-code/challenge tests. These genuinely run and
pass in this environment regardless of PostgreSQL availability.
"""
from apps.accounts.models import UserSession
from apps.accounts.session_utils import build_device_name, get_client_ip, parse_user_agent

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SAFARI_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
EDGE_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
)
CHROME_ANDROID_MOBILE = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
SAFARI_IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


# --------------------------------------------------------------------------
# parse_user_agent
# --------------------------------------------------------------------------


def test_parse_chrome_on_windows():
    device_type, browser, os_name = parse_user_agent(CHROME_WINDOWS)

    assert browser == "Chrome"
    assert os_name == "Windows"
    assert device_type == UserSession.DeviceType.DESKTOP


def test_parse_safari_on_mac():
    device_type, browser, os_name = parse_user_agent(SAFARI_MAC)

    assert browser == "Safari"
    assert os_name == "macOS"
    assert device_type == UserSession.DeviceType.DESKTOP


def test_parse_firefox_on_linux():
    device_type, browser, os_name = parse_user_agent(FIREFOX_LINUX)

    assert browser == "Firefox"
    assert os_name == "Linux"
    assert device_type == UserSession.DeviceType.DESKTOP


def test_parse_edge_not_misidentified_as_chrome():
    """Edge's UA contains 'Chrome/' too — Edge must win."""
    _, browser, os_name = parse_user_agent(EDGE_WINDOWS)

    assert browser == "Edge"
    assert os_name == "Windows"


def test_parse_mobile_chrome_on_android():
    device_type, browser, os_name = parse_user_agent(CHROME_ANDROID_MOBILE)

    assert device_type == UserSession.DeviceType.MOBILE
    assert browser == "Chrome"
    assert os_name == "Android"


def test_parse_iphone_safari():
    device_type, browser, os_name = parse_user_agent(SAFARI_IPHONE)

    assert device_type == UserSession.DeviceType.MOBILE
    assert os_name == "iOS"
    assert browser == "Safari"


def test_parse_ipad_is_tablet():
    device_type, _, os_name = parse_user_agent(SAFARI_IPAD)

    assert device_type == UserSession.DeviceType.TABLET
    assert os_name == "iOS"


def test_parse_empty_user_agent():
    device_type, browser, os_name = parse_user_agent("")

    assert device_type == UserSession.DeviceType.UNKNOWN
    assert browser == "Unknown"
    assert os_name == "Unknown"


def test_parse_none_user_agent():
    device_type, browser, os_name = parse_user_agent(None)

    assert device_type == UserSession.DeviceType.UNKNOWN
    assert browser == "Unknown"
    assert os_name == "Unknown"


def test_parse_unrecognized_user_agent_does_not_raise():
    device_type, browser, os_name = parse_user_agent("SomeUnknownCrawlerBot/1.0")

    assert device_type == UserSession.DeviceType.DESKTOP
    assert browser == "Unknown"
    assert os_name == "Unknown"


# --------------------------------------------------------------------------
# build_device_name
# --------------------------------------------------------------------------


def test_build_device_name():
    assert build_device_name("Chrome", "Windows") == "Chrome on Windows"


def test_build_device_name_unknown():
    assert build_device_name("Unknown", "Unknown") == "Unknown device"


# --------------------------------------------------------------------------
# get_client_ip
# --------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, meta):
        self.META = meta


def test_get_client_ip_prefers_x_forwarded_for():
    request = _FakeRequest({"HTTP_X_FORWARDED_FOR": "203.0.113.5, 10.0.0.1", "REMOTE_ADDR": "10.0.0.1"})

    assert get_client_ip(request) == "203.0.113.5"


def test_get_client_ip_falls_back_to_remote_addr():
    request = _FakeRequest({"REMOTE_ADDR": "127.0.0.1"})

    assert get_client_ip(request) == "127.0.0.1"


def test_get_client_ip_none_request():
    assert get_client_ip(None) is None


def test_get_client_ip_strips_whitespace():
    request = _FakeRequest({"HTTP_X_FORWARDED_FOR": "  203.0.113.5  ,10.0.0.1"})

    assert get_client_ip(request) == "203.0.113.5"
