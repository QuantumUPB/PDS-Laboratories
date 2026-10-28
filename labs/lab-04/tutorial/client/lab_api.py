"""Small OpenSearch HTTP client for the snapshot exercise."""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://opensearch:9200"

OPERATIONS = {
    "register": (
        "PUT",
        "/_snapshot/lab-backups",
        {"type": "s3", "settings": {"bucket": "lab-snapshots"}},
    ),
    "verify": ("POST", "/_snapshot/lab-backups/_verify", None),
    "snapshot": (
        "PUT",
        "/_snapshot/lab-backups/checkpoint-1?wait_for_completion=true",
        {"indices": "lab-logs", "include_global_state": False},
    ),
    "snapshots": ("GET", "/_snapshot/lab-backups/_all", None),
    "search": ("GET", "/lab-logs/_search?pretty", None),
    "delete-sample": ("DELETE", "/lab-logs", None),
    "restore": (
        "POST",
        "/_snapshot/lab-backups/checkpoint-1/_restore?wait_for_completion=true",
        {"indices": "lab-logs", "include_global_state": False},
    ),
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in OPERATIONS:
        print("Usage: python lab_api.py <" + "|".join(OPERATIONS) + ">", file=sys.stderr)
        return 2

    method, path, body = OPERATIONS[sys.argv[1]]
    data = None if body is None else json.dumps(body).encode("utf-8")
    print(f"{method} {path}")
    if body is not None:
        print(json.dumps(body, indent=2))
    req = Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=120) as response:
            print(json.dumps(json.load(response), indent=2))
    except HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Connection failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
