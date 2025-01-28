import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_configured_session() -> requests.Session:
    """Return a requests.Session object with retries configured."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session
