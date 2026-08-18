#!/usr/bin/env python3

import fcntl
import json
import os
import sys
import time


PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"


def main():
    address = os.environ["FREEBUDS_FAKE_ADDRESS"]
    log_path = os.environ["FREEBUDS_FAKE_BRIDGE_LOG"]
    lock_path = os.environ["FREEBUDS_FAKE_BRIDGE_LOCK"]
    startup = os.environ.get("FREEBUDS_FAKE_STARTUP", "valid")
    refresh_delay = float(os.environ.get("FREEBUDS_FAKE_REFRESH_DELAY", "0"))
    if startup not in ("valid", "invalid", "duplicate-invalid"):
        raise ValueError("unsupported fake startup mode")
    if refresh_delay < 0 or refresh_delay > 2:
        raise ValueError("unsupported fake refresh delay")

    def log(event, **fields):
        record = {"event": event}
        record.update(fields)
        with open(log_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")

    def emit(message):
        log("output", type=message["type"], code=message.get("code"))
        sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    lock_stream = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("overlap", pid=os.getpid(), startup=startup)
        return 3

    log("started", pid=os.getpid(), startup=startup)
    try:
        if startup in ("invalid", "duplicate-invalid"):
            emit({
                "v": PROTOCOL_VERSION,
                "type": "error",
                "code": "config_invalid",
            })
        if startup == "duplicate-invalid":
            emit({
                "v": PROTOCOL_VERSION,
                "type": "error",
                "code": "config_invalid",
            })
        emit({
            "v": PROTOCOL_VERSION,
            "type": "hello",
            "bridgeVersion": BRIDGE_VERSION,
            "selectedAddress": None,
        })

        for line in sys.stdin:
            request = json.loads(line)
            method = request.get("method")
            log("request", method=method)

            if method == "refresh":
                time.sleep(refresh_delay)
                emit({
                    "v": PROTOCOL_VERSION,
                    "type": "result",
                    "id": request["id"],
                    "generation": request["generation"],
                    "address": request["address"],
                    "verified": True,
                    "selectedAddress": request["address"],
                    "left": 72,
                    "right": 68,
                    "case": 54,
                    "anc": "anc",
                    "batteryError": None,
                    "ancError": None,
                })
            elif method == "set_anc":
                emit({
                    "v": PROTOCOL_VERSION,
                    "type": "result",
                    "id": request["id"],
                    "generation": request["generation"],
                    "address": request["address"],
                    "verified": True,
                    "anc": request["mode"],
                })
            elif method in ("clear_selection", "shutdown"):
                emit({
                    "v": PROTOCOL_VERSION,
                    "type": "result",
                    "id": request["id"],
                    "generation": request["generation"],
                    "address": None,
                    "selectedAddress": None,
                })
                if method == "shutdown":
                    break
    finally:
        log("stopped", pid=os.getpid())
        lock_stream.close()


if __name__ == "__main__":
    main()
