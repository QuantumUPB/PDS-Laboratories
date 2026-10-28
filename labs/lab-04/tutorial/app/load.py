"""Send repeatable traffic to the lab app."""

from urllib.error import HTTPError
from urllib.request import urlopen


for path in ("/items", "/items", "/missing", "/items", "/missing", "/items"):
    try:
        with urlopen("http://127.0.0.1:8080" + path, timeout=10) as response:
            print(f"{path}: HTTP {response.status}")
    except HTTPError as error:
        print(f"{path}: HTTP {error.code}")
