#!/usr/bin/env python3
"""Strict, offline-testable FreeBuds Pro 5 RFCOMM bridge."""

import binascii
import errno
import fcntl
import json
import math
import os
import re
import select
import socket
import stat
import struct
import sys
import threading
import time


PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"
MAX_FRAME_BYTES = 4096
MAX_JSONL_BYTES = 16 * 1024
MAX_MODEL_VALUE_BYTES = 64
RFCOMM_CHANNEL = 1
BT_SECURITY_MEDIUM_LEVEL = 2
CONNECT_TIMEOUT_SECONDS = 3.0
RESPONSE_TIMEOUT_SECONDS = 2.0
TRANSACTION_TIMEOUT_SECONDS = 10.0
WORKER_JOIN_TIMEOUT_SECONDS = 1.0
CONFIG_LOCK_TIMEOUT_SECONDS = 1.0
CONFIG_LOCK_POLL_SECONDS = 0.01

STARTUP_FRAME = bytes.fromhex("5A00030001063EBD")
DEVICE_INFO_QUERY = bytes.fromhex(
    "5A00210001070100020003000400050006000700080009000A000B000C000F0018001900DFF3"
)
BATTERY_QUERY = bytes.fromhex("5A0009000108010002000300FBB9")
ANC_QUERY = bytes.fromhex("5A0005002B2A0100427E")
SET_ANC_OFF = bytes.fromhex("5A0007002B0401020000D22D")
SET_ANC_ON = bytes.fromhex("5A0007002B04010201FFFFEC")
SET_ANC_AWARENESS = bytes.fromhex("5A0007002B04010202FFAABF")

RETAINED_FRAMES = (
    DEVICE_INFO_QUERY,
    BATTERY_QUERY,
    ANC_QUERY,
    SET_ANC_OFF,
    SET_ANC_ON,
    SET_ANC_AWARENESS,
)

_ANC_WRITE_FRAMES = {
    "off": SET_ANC_OFF,
    "anc": SET_ANC_ON,
    "awareness": SET_ANC_AWARENESS,
}
_FIXED_TRANSPORT_FRAMES = {
    "device_info": DEVICE_INFO_QUERY,
    "battery": BATTERY_QUERY,
    "anc_read": ANC_QUERY,
    "anc_off": SET_ANC_OFF,
    "anc_on": SET_ANC_ON,
    "anc_awareness": SET_ANC_AWARENESS,
}
_ANC_TRANSPORT_OPERATIONS = {
    "off": "anc_off",
    "anc": "anc_on",
    "awareness": "anc_awareness",
}
_ANC_MODE_NAMES = {0: "off", 1: "anc", 2: "awareness"}
_CANONICAL_ADDRESS = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")
_MODEL_VALUE = re.compile(r"^([A-Z0-9]+)-([0-9A-F]{6})$")
_MODEL_PREFIX = re.compile(r"^[A-Z0-9]+$")

ERROR_MESSAGES = {
    "invalid_request": "Invalid private helper request.",
    "busy": "A private request is already in progress.",
    "config_invalid": "Saved device selection is invalid.",
    "config_write_failed": "Could not save device selection.",
    "invalid_address": "Invalid selected device.",
    "transport_unsupported": "Secure private channel is unavailable.",
    "security_failed": "Secure private channel is unavailable.",
    "connect_failed": "Private channel is unavailable.",
    "transport_busy": "Private channel is busy.",
    "timeout": "Private request timed out.",
    "socket_closed": "Private channel closed unexpectedly.",
    "invalid_frame": "Invalid private response.",
    "unexpected_response": "Unexpected private response.",
    "identity_mismatch": "This device is not a verified FreeBuds Pro 5.",
    "identity_conflict": "Device identity fields conflict.",
    "battery_invalid": "Battery components were not reported.",
    "anc_invalid": "Noise control was not reported.",
    "anc_send_failed": "Noise control change was not confirmed.",
    "anc_readback_failed": "Noise control change was not confirmed.",
    "anc_readback_mismatch": "Earbuds reported a different mode.",
}


class BridgeError(Exception):
    """An error safe to expose as a stable protocol code."""

    def __init__(self, code, details=None):
        if code not in ERROR_MESSAGES:
            code = "invalid_request"
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})


def crc16_xmodem(data):
    """Return CRC-16/XMODEM for a bytes-like value."""

    return binascii.crc_hqx(bytes(data), 0)


def validate_retained_frames():
    """Fail if an immutable captured protocol frame was corrupted."""

    for frame in (STARTUP_FRAME,) + RETAINED_FRAMES:
        if len(frame) < 8 or frame[0] != 0x5A:
            raise RuntimeError("retained frame self-check failed")
        declared_length = int.from_bytes(frame[1:3], "big")
        if len(frame) != declared_length + 5:
            raise RuntimeError("retained frame self-check failed")
        if crc16_xmodem(frame[:-2]) != int.from_bytes(frame[-2:], "big"):
            raise RuntimeError("retained frame self-check failed")


def parse_frame(frame_bytes):
    """Parse one exact Huawei frame after length, version, CRC, and TLV checks."""

    if not isinstance(frame_bytes, (bytes, bytearray, memoryview)):
        raise BridgeError("invalid_frame")
    frame = bytes(frame_bytes)
    if len(frame) < 8 or len(frame) > MAX_FRAME_BYTES or frame[0] != 0x5A:
        raise BridgeError("invalid_frame")
    declared_length = int.from_bytes(frame[1:3], "big")
    if declared_length < 3 or declared_length + 5 != len(frame):
        raise BridgeError("invalid_frame")
    if frame[3] != 0x00:
        raise BridgeError("invalid_frame")
    expected_crc = int.from_bytes(frame[-2:], "big")
    if crc16_xmodem(frame[:-2]) != expected_crc:
        raise BridgeError("invalid_frame")

    tlvs = []
    offset = 6
    end = len(frame) - 2
    while offset < end:
        if offset + 2 > end:
            raise BridgeError("invalid_frame")
        tag = frame[offset]
        value_length = frame[offset + 1]
        value_start = offset + 2
        value_end = value_start + value_length
        if value_end > end:
            raise BridgeError("invalid_frame")
        tlvs.append((tag, frame[value_start:value_end]))
        offset = value_end

    return {
        "service": frame[4],
        "command": frame[5],
        "tlvs": tuple(tlvs),
    }


class FrameStreamDecoder:
    """Bounded stream-to-frame decoder with magic-byte resynchronization."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, chunk):
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise BridgeError("invalid_frame")
        self._buffer.extend(chunk)
        frames = []

        while self._buffer:
            magic_at = self._buffer.find(b"\x5A")
            if magic_at < 0:
                self._buffer.clear()
                break
            if magic_at:
                del self._buffer[:magic_at]
            if len(self._buffer) < 3:
                break

            declared_length = int.from_bytes(self._buffer[1:3], "big")
            total_length = declared_length + 5
            if declared_length < 3 or total_length > MAX_FRAME_BYTES:
                self._buffer.clear()
                raise BridgeError("invalid_frame")
            if len(self._buffer) < total_length:
                break

            exact_frame = bytes(self._buffer[:total_length])
            del self._buffer[:total_length]
            frames.append(parse_frame(exact_frame))

        return frames

    def finish(self):
        """Assert that EOF did not truncate a frame."""

        if self._buffer:
            self._buffer.clear()
            raise BridgeError("invalid_frame")

    def clear(self):
        self._buffer.clear()

    @property
    def has_pending_data(self):
        return bool(self._buffer)


def _coerce_frame(frame):
    if isinstance(frame, dict):
        return frame
    return parse_frame(frame)


def _expect_response(frame, service, command):
    parsed = _coerce_frame(frame)
    if parsed.get("service") != service or parsed.get("command") != command:
        raise BridgeError("unexpected_response")
    tlvs = parsed.get("tlvs")
    if not isinstance(tlvs, tuple):
        raise BridgeError("invalid_frame")
    return parsed


def _expect_startup(frame):
    parsed = _expect_response(frame, 0x01, 0x06)
    if parsed["tlvs"]:
        raise BridgeError("unexpected_response")
    return parsed


def _known_tlvs(frame, known_tags, error_code):
    values = {}
    for tag, value in frame["tlvs"]:
        if tag in known_tags:
            if tag in values:
                raise BridgeError(error_code)
            values[tag] = value
    return values


def decode_device_identity(frame):
    """Require the strict private identity for FreeBuds Pro 5 (00016D)."""

    parsed = _expect_response(frame, 0x01, 0x07)
    values = _known_tlvs(parsed, {0x02, 0x0A, 0x0F, 0x19}, "identity_conflict")
    if set(values) != {0x02, 0x0A, 0x0F, 0x19}:
        raise BridgeError("identity_mismatch")
    if len(values[0x02]) != 2 or len(values[0x19]) != 1:
        raise BridgeError("identity_mismatch")
    if not 1 <= len(values[0x0A]) <= MAX_MODEL_VALUE_BYTES:
        raise BridgeError("identity_mismatch")
    if not 1 <= len(values[0x0F]) <= MAX_MODEL_VALUE_BYTES:
        raise BridgeError("identity_mismatch")

    try:
        model_value = values[0x0A].decode("ascii")
        declared_prefix = values[0x0F].decode("ascii")
    except UnicodeDecodeError as error:
        raise BridgeError("identity_mismatch") from error

    match = _MODEL_VALUE.fullmatch(model_value)
    if match is None or _MODEL_PREFIX.fullmatch(declared_prefix) is None:
        raise BridgeError("identity_mismatch")
    model_prefix, model_id = match.groups()
    if model_id != "00016D":
        raise BridgeError("identity_mismatch")

    model_code = values[0x02].hex().upper()
    if model_code != model_id[-4:] or declared_prefix != model_prefix:
        raise BridgeError("identity_conflict")
    return {"verified": True}


def decode_battery(frame):
    """Decode only the retained Pro 5 component-battery shape."""

    parsed = _expect_response(frame, 0x01, 0x08)
    values = _known_tlvs(parsed, {0x02, 0x05}, "battery_invalid")
    components = values.get(0x02)
    presence = values.get(0x05)
    if components is None or len(components) != 3:
        raise BridgeError("battery_invalid")
    if presence is None or len(presence) != 2 or any(value not in (0, 1) for value in presence):
        raise BridgeError("battery_invalid")
    if any(value > 100 for value in components):
        raise BridgeError("battery_invalid")
    return {
        "left": components[0],
        "right": components[1],
        "case": components[2],
    }


def decode_anc(frame):
    """Decode only the extended Pro 5 top-level ANC response shape."""

    parsed = _expect_response(frame, 0x2B, 0x2A)
    values = _known_tlvs(parsed, {0x01, 0x02}, "anc_invalid")
    state = values.get(0x01)
    marker = values.get(0x02)
    if state is None or len(state) != 2 or marker != b"\x05":
        raise BridgeError("anc_invalid")
    mode = _ANC_MODE_NAMES.get(state[1])
    if mode is None:
        raise BridgeError("anc_invalid")
    return {"mode": mode}


def is_canonical_address(address):
    return isinstance(address, str) and _CANONICAL_ADDRESS.fullmatch(address) is not None


def _linux_boottime():
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _socket_input_readable(active_socket):
    readable, _, _ = select.select((active_socket,), (), (), 0)
    return bool(readable)


class RfcommTransport:
    """One Linux medium-security RFCOMM socket, created only on connect()."""

    def __init__(self, socket_factory=None, clock=None, readiness=None):
        self._socket_factory = socket_factory or socket.socket
        self._clock = _linux_boottime if clock is None else clock
        self._readiness = _socket_input_readable if readiness is None else readiness
        self._socket = None
        self._decoder = FrameStreamDecoder()
        self._closed = False
        self._state_lock = threading.Lock()

    def connect(self, address, timeout):
        family = getattr(socket, "AF_BLUETOOTH", None)
        protocol = getattr(socket, "BTPROTO_RFCOMM", None)
        if family is None or protocol is None:
            raise BridgeError("transport_unsupported")
        bluetooth_level = getattr(socket, "SOL_BLUETOOTH", None)
        security_option = getattr(socket, "BT_SECURITY", None)
        if bluetooth_level is None or security_option is None:
            raise BridgeError("security_failed")

        with self._state_lock:
            if self._closed:
                raise BridgeError("socket_closed")
            try:
                active_socket = self._socket_factory(family, socket.SOCK_STREAM, protocol)
            except (AttributeError, OSError) as error:
                raise BridgeError("transport_unsupported") from error
            self._socket = active_socket

        deadline = self._clock() + timeout
        try:
            active_socket.settimeout(timeout)
            security = struct.pack("BB", BT_SECURITY_MEDIUM_LEVEL, 0)
            active_socket.setsockopt(bluetooth_level, security_option, security)
            reported = active_socket.getsockopt(
                bluetooth_level,
                security_option,
                struct.calcsize("BB"),
            )
            if not isinstance(reported, (bytes, bytearray)) or len(reported) < 2:
                raise BridgeError("security_failed")
            reported_level, _ = struct.unpack("BB", bytes(reported[:2]))
            if reported_level < BT_SECURITY_MEDIUM_LEVEL:
                raise BridgeError("security_failed")
        except BridgeError:
            raise
        except (AttributeError, OSError, struct.error) as error:
            raise BridgeError("security_failed") from error

        try:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise BridgeError("timeout")
            active_socket.settimeout(remaining)
            active_socket.connect((address, RFCOMM_CHANNEL))
        except BridgeError:
            raise
        except (socket.timeout, TimeoutError) as error:
            raise BridgeError("timeout") from error
        except OSError as error:
            if error.errno == errno.ETIMEDOUT:
                raise BridgeError("timeout") from error
            busy_errors = {errno.EBUSY, errno.EADDRINUSE, errno.EAGAIN}
            if error.errno in busy_errors:
                raise BridgeError("transport_busy") from error
            raise BridgeError("connect_failed") from error

        remaining = deadline - self._clock()
        if remaining <= 0:
            raise BridgeError("timeout")
        startup = self.receive_frame(remaining)
        _expect_startup(startup)
        if self._clock() > deadline:
            raise BridgeError("timeout")

    def send_device_info_query(self, timeout):
        self._send_fixed_operation("device_info", timeout)

    def send_battery_query(self, timeout):
        self._send_fixed_operation("battery", timeout)

    def send_anc_query(self, timeout):
        self._send_fixed_operation("anc_read", timeout)

    def send_anc_write(self, mode, timeout):
        if type(mode) is not str or mode not in _ANC_TRANSPORT_OPERATIONS:
            raise BridgeError("invalid_request")
        self._send_fixed_operation(_ANC_TRANSPORT_OPERATIONS[mode], timeout)

    def _send_fixed_operation(self, operation, timeout):
        active_socket = self._current_socket()
        self._assert_no_prior_input(active_socket)
        try:
            active_socket.settimeout(timeout)
            active_socket.sendall(_FIXED_TRANSPORT_FRAMES[operation])
        except (socket.timeout, TimeoutError) as error:
            raise BridgeError("timeout") from error
        except OSError as error:
            if error.errno == errno.ETIMEDOUT:
                raise BridgeError("timeout") from error
            raise BridgeError("socket_closed") from error

    def _assert_no_prior_input(self, active_socket):
        # Huawei frames carry no sequence value. This boundary rejects input
        # already visible before a send, but cannot prove causality after it.
        try:
            prior_input = self._readiness(active_socket)
        except BridgeError:
            raise
        except (OSError, TypeError, ValueError) as error:
            raise BridgeError("socket_closed") from error
        if prior_input:
            raise BridgeError("unexpected_response")

    def receive_frame(self, timeout):
        active_socket = self._current_socket()

        deadline = self._clock() + timeout
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise BridgeError("timeout")
            try:
                active_socket.settimeout(remaining)
                chunk = active_socket.recv(MAX_FRAME_BYTES)
            except (socket.timeout, TimeoutError) as error:
                raise BridgeError("timeout") from error
            except OSError as error:
                if error.errno == errno.ETIMEDOUT:
                    raise BridgeError("timeout") from error
                raise BridgeError("socket_closed") from error
            if not chunk:
                try:
                    self._decoder.finish()
                except BridgeError:
                    raise
                raise BridgeError("socket_closed")
            frames = self._decoder.feed(chunk)
            if len(frames) > 1 or (frames and self._decoder.has_pending_data):
                self._decoder.clear()
                raise BridgeError("unexpected_response")
            if frames:
                return frames[0]

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            active_socket = self._socket
            self._socket = None
        self._decoder.clear()
        if active_socket is not None:
            try:
                active_socket.close()
            except OSError:
                pass

    def _current_socket(self):
        with self._state_lock:
            if self._socket is None or self._closed:
                raise BridgeError("socket_closed")
            return self._socket


class TransactionController:
    """Synchronous one-socket controller for refresh and ANC transactions."""

    def __init__(self, transport_factory=None, clock=None):
        self._clock = _linux_boottime if clock is None else clock
        self._transport_factory = transport_factory or (
            lambda: RfcommTransport(clock=self._clock)
        )
        self._active_lock = threading.Lock()
        self._active_transport = None
        self._active_closed = False
        self._claimed = False
        self._cancel_requested = False

    def refresh(self, address):
        if not is_canonical_address(address):
            raise BridgeError("invalid_address")

        def operation(transport, deadline):
            identity = self._query(
                transport,
                transport.send_device_info_query,
                0x01,
                0x07,
                deadline,
            )
            decode_device_identity(identity)

            battery = None
            battery_error = None
            anc = None
            anc_error = None

            try:
                battery_frame = self._query(
                    transport,
                    transport.send_battery_query,
                    0x01,
                    0x08,
                    deadline,
                )
                battery = decode_battery(battery_frame)
                battery["observedAt"] = self._observation_time(deadline)
            except BridgeError as error:
                battery_error = error.code
                if error.code != "battery_invalid":
                    raise

            try:
                anc_frame = self._query(
                    transport,
                    transport.send_anc_query,
                    0x2B,
                    0x2A,
                    deadline,
                )
                anc = decode_anc(anc_frame)
                anc["observedAt"] = self._observation_time(deadline)
            except BridgeError as error:
                anc_error = error.code
                if battery is None and error.code != "anc_invalid":
                    raise

            if battery is None and anc is None:
                raise BridgeError(anc_error or battery_error or "anc_invalid")
            return {
                "identityVerified": True,
                "readVerified": True,
                "battery": battery,
                "batteryError": battery_error,
                "anc": anc,
                "ancError": anc_error,
            }

        return self._run(address, operation)

    def set_anc(self, address, mode):
        if not is_canonical_address(address):
            raise BridgeError("invalid_address")
        if type(mode) is not str or mode not in _ANC_WRITE_FRAMES:
            raise BridgeError("invalid_request")

        def operation(transport, deadline):
            identity = self._query(
                transport,
                transport.send_device_info_query,
                0x01,
                0x07,
                deadline,
            )
            decode_device_identity(identity)
            current_frame = self._query(
                transport,
                transport.send_anc_query,
                0x2B,
                0x2A,
                deadline,
            )
            current = decode_anc(current_frame)
            if current["mode"] == mode:
                current["observedAt"] = self._observation_time(deadline)
                return {
                    "identityVerified": True,
                    "success": True,
                    "anc": current,
                    "writePerformed": False,
                }

            try:
                self._send(
                    lambda timeout: transport.send_anc_write(mode, timeout),
                    deadline,
                )
            except BridgeError as error:
                raise BridgeError("anc_send_failed") from error

            try:
                readback_frame = self._query(
                    transport,
                    transport.send_anc_query,
                    0x2B,
                    0x2A,
                    deadline,
                )
                readback = decode_anc(readback_frame)
            except BridgeError as error:
                raise BridgeError("anc_readback_failed") from error

            observed_at = self._observation_time(deadline)
            if readback["mode"] != mode:
                raise BridgeError(
                    "anc_readback_mismatch",
                    {
                        "observedMode": readback["mode"],
                        "observedAt": observed_at,
                    },
                )
            readback["observedAt"] = observed_at
            return {
                "identityVerified": True,
                "success": True,
                "anc": readback,
                "writePerformed": True,
            }

        return self._run(address, operation)

    def cancel(self):
        transport = None
        with self._active_lock:
            self._cancel_requested = True
            if self._active_transport is not None and not self._active_closed:
                self._active_closed = True
                transport = self._active_transport
        if transport is not None:
            transport.close()

    def _run(self, address, operation):
        with self._active_lock:
            if self._claimed:
                raise BridgeError("busy")
            if self._cancel_requested:
                self._cancel_requested = False
                raise BridgeError("socket_closed")
            self._claimed = True

        transport = None
        try:
            transport = self._transport_factory()
            cancelled = False
            with self._active_lock:
                self._active_transport = transport
                self._active_closed = False
                if self._cancel_requested:
                    self._cancel_requested = False
                    self._active_closed = True
                    cancelled = True
            if cancelled:
                transport.close()
                raise BridgeError("socket_closed")
            started = self._clock()
            deadline = started + TRANSACTION_TIMEOUT_SECONDS
            connect_timeout = min(CONNECT_TIMEOUT_SECONDS, self._remaining(deadline))
            connect_deadline = self._clock() + connect_timeout
            with self._active_lock:
                cancelled = self._cancel_requested or self._active_closed
                self._cancel_requested = False
            if cancelled:
                raise BridgeError("socket_closed")
            transport.connect(address, connect_timeout)
            if self._clock() > connect_deadline:
                raise BridgeError("timeout")
            self._remaining(deadline)
            return operation(transport, deadline)
        except BridgeError:
            raise
        except (socket.timeout, TimeoutError) as error:
            raise BridgeError("timeout") from error
        except OSError as error:
            raise BridgeError("socket_closed") from error
        finally:
            self._close_active_once(transport)
            with self._active_lock:
                self._active_transport = None
                self._active_closed = False
                self._claimed = False
                self._cancel_requested = False

    def _close_active_once(self, transport):
        if transport is not None:
            transport.close()

    def _query(self, transport, send_action, service, command, deadline):
        self._send(send_action, deadline)
        response_timeout = min(RESPONSE_TIMEOUT_SECONDS, self._remaining(deadline))
        response_deadline = self._clock() + response_timeout
        frame = transport.receive_frame(response_timeout)
        if self._clock() > response_deadline:
            raise BridgeError("timeout")
        self._remaining(deadline)
        return _expect_response(frame, service, command)

    def _send(self, send_action, deadline):
        send_action(self._remaining(deadline))
        self._remaining(deadline)

    def _remaining(self, deadline):
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise BridgeError("timeout")
        return remaining

    def _observation_time(self, deadline):
        observed_at = self._clock()
        if observed_at > deadline:
            raise BridgeError("timeout")
        return observed_at


def default_config_path(environ=None):
    environment = os.environ if environ is None else environ
    config_home = environment.get("XDG_CONFIG_HOME")
    if not config_home:
        home = environment.get("HOME")
        if not home:
            raise BridgeError("config_invalid")
        config_home = os.path.join(home, ".config")
    return os.path.join(
        config_home,
        "omarchy",
        "io.github.filipechagas.freebuds.json",
    )


def _reject_json_constant(_value):
    raise ValueError("non-finite JSON number")


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _strict_json_object(raw):
    try:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8")
        elif isinstance(raw, str):
            text = raw
        else:
            raise ValueError("JSON input must be bytes or text")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ValueError("invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("JSON value must be an object")
    return value


class _SelectionLease:
    def __init__(self, descriptor, address, error):
        self._descriptor = descriptor
        self.address = address
        self.error = error

    def __enter__(self):
        return self.address, self.error

    def __exit__(self, _error_type, _error, _traceback):
        if self._descriptor >= 0:
            os.close(self._descriptor)
            self._descriptor = -1


class ConfigStore:
    """Atomic owner-only storage for the single selected transport address."""

    def __init__(self, path=None, environ=None, clock=None, sleep=None):
        self.path = path or default_config_path(environ)
        self._parent = os.path.dirname(self.path) or "."
        self._name = os.path.basename(self.path)
        self._clock = _linux_boottime if clock is None else clock
        self._sleep = time.sleep if sleep is None else sleep

    def load(self):
        parent_descriptor = -1
        try:
            parent_descriptor = self._open_parent(create=False)
            if parent_descriptor is None:
                return None, None
            self._acquire_flock(parent_descriptor, fcntl.LOCK_SH)
            return self._load_locked(parent_descriptor)
        except (OSError, ValueError):
            return None, "config_invalid"
        finally:
            if parent_descriptor is not None and parent_descriptor >= 0:
                os.close(parent_descriptor)

    def selection_lease(self):
        parent_descriptor = -1
        try:
            parent_descriptor = self._open_parent(create=False)
            if parent_descriptor is None:
                return _SelectionLease(-1, None, None)
            self._acquire_flock(parent_descriptor, fcntl.LOCK_SH)
            address, error = self._load_locked(parent_descriptor)
            lease = _SelectionLease(parent_descriptor, address, error)
            parent_descriptor = -1
            return lease
        except (OSError, ValueError):
            return _SelectionLease(-1, None, "config_invalid")
        finally:
            if parent_descriptor is not None and parent_descriptor >= 0:
                os.close(parent_descriptor)

    def _load_locked(self, parent_descriptor):
        try:
            before = self._entry_stat(parent_descriptor)
        except FileNotFoundError:
            return None, None
        if not self._valid_file_stat(before):
            return None, "config_invalid"

        descriptor = os.open(
            self._name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
        try:
            opened = os.fstat(descriptor)
            if (
                not self._valid_file_stat(opened)
                or not self._same_identity(before, opened)
            ):
                return None, "config_invalid"
            with os.fdopen(descriptor, "rb", closefd=True) as config_file:
                descriptor = -1
                raw = config_file.read(MAX_JSONL_BYTES + 1)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        current = self._entry_stat(parent_descriptor)
        if not self._same_identity(opened, current):
            return None, "config_invalid"

        if len(raw) > MAX_JSONL_BYTES:
            return None, "config_invalid"
        try:
            value = _strict_json_object(raw)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return None, "config_invalid"
        if set(value) != {"schemaVersion", "selectedAddress"}:
            return None, "config_invalid"
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
            return None, "config_invalid"
        address = value["selectedAddress"]
        if not is_canonical_address(address):
            return None, "config_invalid"
        return address, None

    def save(self, address):
        if not is_canonical_address(address):
            raise BridgeError("invalid_address")
        parent_descriptor = -1
        temporary_name = None
        descriptor = -1
        installed_identity = None
        install_attempted = False
        try:
            parent_descriptor = self._open_parent(create=True)
            self._acquire_flock(parent_descriptor, fcntl.LOCK_EX)
            try:
                target_stat = self._entry_stat(parent_descriptor)
            except FileNotFoundError:
                target_stat = None
            if target_stat is not None:
                if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
                    raise OSError("unsafe config target")
                if target_stat.st_uid != os.geteuid():
                    raise OSError("config target has another owner")

            descriptor, temporary_name = self._create_temporary(
                parent_descriptor,
                "write",
            )
            payload = json.dumps(
                {"schemaVersion": 1, "selectedAddress": address},
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
            # Keep the inode pinned until post-replace verification and rollback finish.
            with os.fdopen(os.dup(descriptor), "wb", closefd=True) as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_stat = os.fstat(descriptor)
                installed_identity = (temporary_stat.st_dev, temporary_stat.st_ino)
            install_attempted = True
            os.replace(
                temporary_name,
                self._name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
            temporary_name = None
            target_descriptor = os.open(
                self._name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_descriptor,
            )
            try:
                persisted_stat = os.fstat(target_descriptor)
                if (
                    not self._valid_file_stat(persisted_stat)
                    or (persisted_stat.st_dev, persisted_stat.st_ino)
                    != installed_identity
                ):
                    raise OSError("unsafe persisted config target")
                installed_stat = self._entry_stat(parent_descriptor)
                if not self._same_identity(persisted_stat, installed_stat):
                    raise OSError("persisted config target was replaced")
                os.fsync(target_descriptor)
            finally:
                os.close(target_descriptor)
            os.fsync(parent_descriptor)
            install_attempted = False
        except (OSError, ValueError) as error:
            if temporary_name is not None and parent_descriptor >= 0:
                try:
                    os.unlink(temporary_name, dir_fd=parent_descriptor)
                except OSError:
                    pass
            if (
                install_attempted
                and installed_identity is not None
                and parent_descriptor >= 0
            ):
                self._rollback_installed(parent_descriptor, installed_identity)
            raise BridgeError("config_write_failed") from error
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if parent_descriptor >= 0:
                os.close(parent_descriptor)

    def clear(self):
        parent_descriptor = -1
        try:
            parent_descriptor = self._open_parent(create=False)
        except OSError as error:
            raise BridgeError("config_invalid") from error
        if parent_descriptor is None:
            return
        try:
            self._acquire_flock(parent_descriptor, fcntl.LOCK_EX)
            try:
                target_stat = self._entry_stat(parent_descriptor)
            except FileNotFoundError:
                return
            if (
                stat.S_ISLNK(target_stat.st_mode)
                or not stat.S_ISREG(target_stat.st_mode)
                or target_stat.st_uid != os.geteuid()
            ):
                raise BridgeError("config_invalid")
            identity = (target_stat.st_dev, target_stat.st_ino)
            if not self._remove_entry_if_identity(parent_descriptor, identity):
                raise OSError("config target changed during clear")
            os.fsync(parent_descriptor)
        except BridgeError:
            raise
        except OSError as error:
            raise BridgeError("config_write_failed") from error
        finally:
            os.close(parent_descriptor)

    @staticmethod
    def _valid_file_stat(file_stat):
        return (
            stat.S_ISREG(file_stat.st_mode)
            and not stat.S_ISLNK(file_stat.st_mode)
            and file_stat.st_uid == os.geteuid()
            and stat.S_IMODE(file_stat.st_mode) == 0o600
        )

    @staticmethod
    def _same_identity(first, second):
        return first.st_dev == second.st_dev and first.st_ino == second.st_ino

    def _entry_stat(self, parent_descriptor, name=None):
        return os.stat(
            self._name if name is None else name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )

    def _open_parent(self, create):
        if create:
            os.makedirs(self._parent, mode=0o700, exist_ok=True)
        try:
            descriptor = os.open(
                self._parent,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except FileNotFoundError:
            if not create:
                return None
            raise
        try:
            parent_stat = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(parent_stat.st_mode)
                or parent_stat.st_uid != os.geteuid()
                or stat.S_IMODE(parent_stat.st_mode) & 0o022
            ):
                raise OSError("unsafe config directory")
        except Exception:
            os.close(descriptor)
            raise
        return descriptor

    def _acquire_flock(self, descriptor, operation):
        deadline = self._clock() + CONFIG_LOCK_TIMEOUT_SECONDS
        first_attempt = True
        while True:
            if not first_attempt and self._clock() >= deadline:
                raise TimeoutError(errno.ETIMEDOUT, "config lock timed out")
            first_attempt = False
            try:
                fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
                return
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise TimeoutError(errno.ETIMEDOUT, "config lock timed out")
            self._sleep(min(CONFIG_LOCK_POLL_SECONDS, remaining))

    def _create_temporary(self, parent_descriptor, purpose):
        token = binascii.hexlify(os.urandom(16)).decode("ascii")
        name = ".{}.{}.{}".format(self._name, purpose, token)
        descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_descriptor,
        )
        try:
            os.fchmod(descriptor, 0o600)
            temporary_stat = os.fstat(descriptor)
            if not self._valid_file_stat(temporary_stat):
                raise OSError("unsafe temporary config target")
        except Exception:
            os.close(descriptor)
            try:
                os.unlink(name, dir_fd=parent_descriptor)
            except OSError:
                pass
            raise
        return descriptor, name

    def _remove_entry_if_identity(self, parent_descriptor, expected_identity):
        try:
            current = self._entry_stat(parent_descriptor)
        except FileNotFoundError:
            return False
        if (current.st_dev, current.st_ino) != expected_identity:
            return False

        quarantine_descriptor = -1
        quarantine_name = None
        moved_entry = False
        preserve_quarantine = False
        try:
            quarantine_descriptor, quarantine_name = self._create_temporary(
                parent_descriptor,
                "rollback",
            )
            os.close(quarantine_descriptor)
            quarantine_descriptor = -1
            try:
                os.rename(
                    self._name,
                    quarantine_name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
            except FileNotFoundError:
                return False
            moved_entry = True
            moved_stat = self._entry_stat(parent_descriptor, quarantine_name)
            if (moved_stat.st_dev, moved_stat.st_ino) == expected_identity:
                os.unlink(quarantine_name, dir_fd=parent_descriptor)
                moved_entry = False
                return True

            # A non-cooperating writer raced the advisory lock. Restore its
            # inode without replacing any newer target and never unlink it
            # unless the target hard link was restored successfully.
            preserve_quarantine = True
            try:
                os.link(
                    quarantine_name,
                    self._name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError:
                return False
            os.unlink(quarantine_name, dir_fd=parent_descriptor)
            moved_entry = False
            preserve_quarantine = False
            return False
        finally:
            if quarantine_descriptor >= 0:
                os.close(quarantine_descriptor)
            if quarantine_name is not None and not moved_entry and not preserve_quarantine:
                try:
                    os.unlink(quarantine_name, dir_fd=parent_descriptor)
                except OSError:
                    pass

    def _rollback_installed(self, parent_descriptor, installed_identity):
        try:
            if self._remove_entry_if_identity(parent_descriptor, installed_identity):
                os.fsync(parent_descriptor)
        except OSError:
            pass


def _valid_request_number(value):
    return type(value) is int and 0 <= value <= (1 << 53) - 1


def validate_request(value):
    if not isinstance(value, dict):
        raise BridgeError("invalid_request")
    common = {"v", "type", "id", "generation", "method"}
    if type(value.get("v")) is not int or value.get("v") != PROTOCOL_VERSION:
        raise BridgeError("invalid_request")
    if value.get("type") != "request":
        raise BridgeError("invalid_request")
    if not _valid_request_number(value.get("id")):
        raise BridgeError("invalid_request")
    if not _valid_request_number(value.get("generation")):
        raise BridgeError("invalid_request")
    method = value.get("method")

    if method == "refresh":
        if set(value) != common | {"address", "selectOnSuccess"}:
            raise BridgeError("invalid_request")
        if not isinstance(value.get("address"), str):
            raise BridgeError("invalid_request")
        if not is_canonical_address(value["address"]):
            raise BridgeError("invalid_address")
        if type(value.get("selectOnSuccess")) is not bool:
            raise BridgeError("invalid_request")
    elif method == "set_anc":
        if set(value) != common | {"address", "mode"}:
            raise BridgeError("invalid_request")
        if not isinstance(value.get("address"), str):
            raise BridgeError("invalid_request")
        if not is_canonical_address(value["address"]):
            raise BridgeError("invalid_address")
        mode = value.get("mode")
        if type(mode) is not str or mode not in _ANC_WRITE_FRAMES:
            raise BridgeError("invalid_request")
    elif method in ("clear_selection", "shutdown"):
        if set(value) != common:
            raise BridgeError("invalid_request")
    else:
        raise BridgeError("invalid_request")
    return value


class JsonlProcess:
    """Bounded JSONL loop that keeps reading while one transaction runs."""

    def __init__(self, controller=None, config_store=None):
        self._controller = controller or TransactionController()
        self._config = config_store or ConfigStore()
        self._output = None
        self._errors = None
        self._output_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._active_id = None
        self._active_thread = None
        self._workers = set()
        self._stopping = threading.Event()
        self._last_request_id = -1
        self._selected_address = None
        self._config_error = None

    def serve(self, input_stream, output_stream, error_stream):
        self._output = output_stream
        self._errors = error_stream
        try:
            self._selected_address, self._config_error = self._config.load()
            if self._config_error is not None:
                self._diagnose(self._config_error)
                self._write_json(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "error",
                        "code": "config_invalid",
                    }
                )
            self._write_json(
                {
                    "v": PROTOCOL_VERSION,
                    "type": "hello",
                    "bridgeVersion": BRIDGE_VERSION,
                    "selectedAddress": self._selected_address,
                }
            )

            keep_running = True
            while keep_running:
                line, overlong = self._read_line(input_stream)
                if line is None:
                    break
                if overlong:
                    self._emit_error(None, None, BridgeError("invalid_request"))
                    continue
                request_id = None
                generation = None
                try:
                    value = _strict_json_object(line)
                    if _valid_request_number(value.get("id")):
                        request_id = value["id"]
                    if _valid_request_number(value.get("generation")):
                        generation = value["generation"]
                except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                    self._emit_error(request_id, generation, BridgeError("invalid_request"))
                    continue
                try:
                    request = validate_request(value)
                except BridgeError as error:
                    self._emit_error(request_id, generation, error)
                    continue
                if request["id"] <= self._last_request_id:
                    self._emit_error(
                        request["id"],
                        request["generation"],
                        BridgeError("invalid_request"),
                        request.get("address"),
                    )
                    continue
                self._last_request_id = request["id"]
                keep_running = self._dispatch(request)
            return 0
        finally:
            self._stop_and_join_workers()

    def _stop_and_join_workers(self):
        self._stopping.set()
        try:
            self._controller.cancel()
        finally:
            with self._state_lock:
                workers = tuple(self._workers)
            join_deadline = time.monotonic() + WORKER_JOIN_TIMEOUT_SECONDS
            for worker in workers:
                if worker is threading.current_thread():
                    continue
                worker.join(max(0.0, join_deadline - time.monotonic()))

    def _dispatch(self, request):
        request_id = request["id"]
        generation = request["generation"]
        dispatch_error = None
        worker = None
        with self._state_lock:
            if self._active_id is not None:
                code = "invalid_request" if self._active_id == request_id else "busy"
                dispatch_error = BridgeError(code)
            elif request["method"] in ("refresh", "set_anc"):
                self._active_id = request_id
                worker = threading.Thread(
                    target=self._run_transaction,
                    args=(request,),
                    name="freebuds-transaction",
                    daemon=True,
                )
                self._active_thread = worker
                self._workers.add(worker)

        if dispatch_error is not None:
            self._emit_error(
                request_id,
                generation,
                dispatch_error,
                request.get("address"),
            )
            return True

        if worker is not None:
            try:
                worker.start()
            except RuntimeError:
                with self._state_lock:
                    if self._active_thread is worker:
                        self._active_id = None
                        self._active_thread = None
                    self._workers.discard(worker)
                self._emit_error(
                    request_id,
                    generation,
                    BridgeError("socket_closed"),
                    request.get("address"),
                )
            return True

        if request["method"] == "clear_selection":
            try:
                self._config.clear()
                self._selected_address = None
                self._config_error = None
                self._emit_result(
                    request,
                    {"address": None, "selectedAddress": None},
                )
            except BridgeError as error:
                self._emit_error(request_id, generation, error)
            return True

        self._emit_result(request, {"address": None, "selectedAddress": None})
        return False

    def _run_transaction(self, request):
        worker = threading.current_thread()
        terminal_error = None
        payload = None
        try:
            try:
                payload = self._execute_transaction(request)
            except BridgeError as error:
                terminal_error = error
            except Exception:
                terminal_error = BridgeError("socket_closed")

            if terminal_error is None:
                terminal = self._result_message(request, payload)
            else:
                terminal = self._error_message(
                    request["id"],
                    request["generation"],
                    terminal_error,
                    request["address"],
                )
                self._diagnose(terminal_error.code)
            self._publish_transaction_terminal(worker, terminal)
        finally:
            with self._state_lock:
                self._workers.discard(worker)
                if self._active_thread is worker:
                    self._active_id = None
                    self._active_thread = None

    def _publish_transaction_terminal(self, worker, value):
        encoded = self._encode_json(value)
        with self._output_lock:
            self._release_active_for_terminal(worker)
            self._write_encoded_locked(encoded)

    def _release_active_for_terminal(self, worker):
        with self._state_lock:
            if self._active_thread is worker:
                self._active_id = None

    def _execute_transaction(self, request):
        method = request["method"]
        address = request["address"]

        if method == "set_anc":
            with self._config.selection_lease() as selection:
                self._selected_address, self._config_error = selection
                if self._selected_address is None:
                    raise BridgeError(
                        "config_invalid" if self._config_error else "invalid_address"
                    )
                if address != self._selected_address:
                    raise BridgeError("invalid_address")
                result = self._controller.set_anc(address, request["mode"])
            return {
                "address": address,
                "verified": result.get("identityVerified") is True,
                "anc": result["anc"]["mode"],
            }

        select_on_success = request["selectOnSuccess"]
        if not select_on_success:
            with self._config.selection_lease() as selection:
                self._selected_address, self._config_error = selection
                if self._selected_address is None:
                    raise BridgeError(
                        "config_invalid" if self._config_error else "invalid_address"
                    )
                if address != self._selected_address:
                    raise BridgeError("invalid_address")
                result = self._controller.refresh(address)
        else:
            result = self._controller.refresh(address)
        if select_on_success:
            self._config.save(address)
            self._selected_address = address
            self._config_error = None
        battery = result.get("battery")
        anc = result.get("anc")
        return {
            "address": address,
            "verified": result.get("identityVerified") is True and result.get("readVerified") is True,
            "selectedAddress": address,
            "left": battery["left"] if battery is not None else None,
            "right": battery["right"] if battery is not None else None,
            "case": battery["case"] if battery is not None else None,
            "anc": anc["mode"] if anc is not None else None,
            "batteryError": result.get("batteryError"),
            "ancError": result.get("ancError"),
        }

    def _emit_result(self, request, payload):
        self._write_json(self._result_message(request, payload))

    @staticmethod
    def _result_message(request, payload):
        result = {
            "v": PROTOCOL_VERSION,
            "type": "result",
            "id": request["id"],
            "generation": request["generation"],
        }
        result.update(payload)
        return result

    def _emit_error(self, request_id, generation, error, address=None):
        payload = self._error_message(request_id, generation, error, address)
        self._diagnose(error.code)
        self._write_json(payload)

    @staticmethod
    def _error_message(request_id, generation, error, address=None):
        payload = {
            "v": PROTOCOL_VERSION,
            "type": "error",
            "id": request_id,
            "generation": generation,
            "address": address if is_canonical_address(address) else None,
            "code": error.code,
            "observedAnc": None,
        }
        if error.code == "anc_readback_mismatch":
            observed_mode = error.details.get("observedMode")
            observed_at = error.details.get("observedAt")
            if (
                type(observed_mode) is str
                and observed_mode in _ANC_WRITE_FRAMES
                and type(observed_at) in (int, float)
                and math.isfinite(observed_at)
            ):
                payload["observedAnc"] = observed_mode
        return payload

    def _write_json(self, value):
        encoded = self._encode_json(value)
        with self._output_lock:
            self._write_encoded_locked(encoded)

    @staticmethod
    def _encode_json(value):
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        if len(encoded) > MAX_JSONL_BYTES:
            raise BridgeError("invalid_request")
        return encoded

    def _write_encoded_locked(self, encoded):
        if self._stopping.is_set():
            return
        self._output.write(encoded)
        self._output.flush()

    def _diagnose(self, code):
        if self._errors is None:
            return
        safe_code = code if code in ERROR_MESSAGES else "invalid_request"
        encoded = ("bridge: " + safe_code + "\n").encode("ascii")
        with self._output_lock:
            if self._stopping.is_set():
                return
            self._errors.write(encoded[:256])
            self._errors.flush()

    @staticmethod
    def _read_line(input_stream):
        line = input_stream.readline(MAX_JSONL_BYTES + 1)
        if line == b"" or line == "":
            return None, False
        if isinstance(line, str):
            line = line.encode("utf-8")
        if len(line) <= MAX_JSONL_BYTES:
            return line, False

        while not line.endswith(b"\n"):
            line = input_stream.readline(MAX_JSONL_BYTES + 1)
            if line == b"" or line == "":
                break
            if isinstance(line, str):
                line = line.encode("utf-8")
        return b"", True


def _write_startup_diagnostic(error_stream, code):
    error_stream.write(("bridge: " + code + "\n").encode("ascii"))
    error_stream.flush()


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else list(argv)
    errors = sys.stderr.buffer
    if arguments != ["--stdio"]:
        _write_startup_diagnostic(errors, "invalid_request")
        return 2
    try:
        validate_retained_frames()
    except Exception:
        _write_startup_diagnostic(errors, "invalid_frame")
        return 1
    try:
        process = JsonlProcess()
    except BridgeError as error:
        _write_startup_diagnostic(errors, error.code)
        return 1
    except Exception:
        _write_startup_diagnostic(errors, "config_invalid")
        return 1
    return process.serve(sys.stdin.buffer, sys.stdout.buffer, errors)


if __name__ == "__main__":
    raise SystemExit(main())
