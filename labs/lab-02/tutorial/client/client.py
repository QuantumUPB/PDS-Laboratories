import os
from pathlib import Path
from urllib.request import urlopen

SERVER_HOST = os.getenv("SERVER_HOST", "server")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", "/data/messages.txt"))


def main():
    url = f"http://{SERVER_HOST}:{SERVER_PORT}/"
    with urlopen(url, timeout=5) as response:
        message = response.read().decode("utf-8")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("a", encoding="utf-8") as output:
        output.write(message)
    print(f"Received: {message.strip()}", flush=True)
    print(f"Appended to {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Client failed: {error}")
