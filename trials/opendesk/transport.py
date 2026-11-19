"""One normal HTTP request inside the trial-only Docker network."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    call = json.load(sys.stdin)
    headers = {"Content-Type": "application/json"}
    if call["token"]:
        headers["Authorization"] = "Bearer " + call["token"]
    if call["workspace"]:
        headers["OD-Workspace"] = call["workspace"]
    body = None if call["body"] is None else json.dumps(call["body"]).encode()
    request = Request(
        "http://app:8080/v1" + call["path"],
        data=body,
        method=call["method"],
        headers=headers,
    )
    try:
        response = urlopen(request, timeout=30)
    except HTTPError as exc:
        response = exc
    with response:
        raw = response.read()
        json.dump([response.status, json.loads(raw) if raw else {}], sys.stdout)


if __name__ == "__main__":
    main()
