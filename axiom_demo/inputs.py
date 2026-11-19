"""Read bounded evidence files and hash the exact bytes used for JSON decoding."""

import hashlib
import json
import os
import stat

from .report import InvalidReport

MAX_JSON_BYTES = 1024 * 1024


def regular_file_opener(path, flags):
    # A nonblocking open lets us inspect the actual descriptor even for a FIFO.
    fd = os.open(path, flags | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise InvalidReport("Input must be a regular file.")
    except BaseException:
        os.close(fd)
        raise
    return fd


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidReport("Duplicate JSON field.")
        result[key] = value
    return result


def read_json(path, label):
    try:
        with open(path, "rb", opener=regular_file_opener) as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
    except OSError:
        raise InvalidReport(f"Could not read {label} input.") from None
    if len(raw) > MAX_JSON_BYTES:
        raise InvalidReport(f"The {label} input exceeds the 1 MiB limit.")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        raise InvalidReport(
            f"Invalid {label} JSON. Use UTF-8 and unique fields."
        ) from None
    return data, hashlib.sha256(raw).hexdigest()
