import binascii
import errno
import socket
import threading
import unittest
from unittest import mock

from bridge import freebuds_bridge as bridge


ADDRESS = "AA:BB:CC:DD:EE:FF"
CAPTURED_BATTERY = bytes.fromhex(
    "5A001B0001080101640203646455030300000004020A140502000106010A4D9B"
)
CAPTURED_ANC = {
    "off": bytes.fromhex("5A000A002B2A01020000020105B843"),
    "anc": bytes.fromhex("5A000A002B2A010203010201052025"),
    "awareness": bytes.fromhex("5A000A002B2A0102020202010511A8"),
}
CAPTURED_ANC_WRITE_ACK = bytes.fromhex("5A0006002B040201003171")


def no_prior_input(_active_socket):
    return False


def frame(service, command, tlvs=()):
    body = bytes((0, service, command))
    for tag, value in tlvs:
        body += bytes((tag, len(value))) + value
    prefix = b"\x5A" + len(body).to_bytes(2, "big") + body
    return prefix + binascii.crc_hqx(prefix, 0).to_bytes(2, "big")


def identity(model_id="00016D", prefix=b"BTF0027", model_code=None):
    if model_code is None:
        model_code = bytes.fromhex(model_id[-4:])
    return frame(
        1,
        7,
        [
            (2, model_code),
            (0x0A, prefix + b"-" + model_id.encode("ascii")),
            (0x0F, prefix),
            (0x19, b"\x02"),
        ],
    )


INVALID_BATTERY_SHAPE = frame(1, 8, [(2, b"\x64\x64\x55")])
INVALID_ANC_SHAPE = bytes.fromhex("5A0007002B2A010203015043")
STARTUP_FRAME = frame(1, 6)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class ScriptedTransport:
    def __init__(
        self,
        responses=(),
        clock=None,
        connect_error=None,
        connect_advance=0,
        send_errors=None,
        send_advances=None,
        receive_advances=None,
    ):
        self.responses = list(responses)
        self.clock = clock
        self.connect_error = connect_error
        self.connect_advance = connect_advance
        self.send_errors = dict(send_errors or {})
        self.send_advances = list(send_advances or [])
        self.receive_advances = list(receive_advances or [])
        self.events = []
        self.sent = []
        self.connect_calls = []
        self.receive_timeouts = []
        self.close_calls = 0
        self.closed = False

    def connect(self, address, timeout):
        self.events.append("connect")
        self.connect_calls.append((address, timeout))
        if self.clock is not None:
            self.clock.advance(self.connect_advance)
        if self.connect_error is not None:
            raise self.connect_error

    def _record_send(self, payload, timeout):
        index = len(self.sent)
        self.events.append(("send", payload))
        self.sent.append(payload)
        if self.clock is not None and index < len(self.send_advances):
            self.clock.advance(self.send_advances[index])
        error = self.send_errors.get(index)
        if error is not None:
            raise error

    def send_device_info_query(self, timeout):
        self._record_send(bridge.DEVICE_INFO_QUERY, timeout)

    def send_battery_query(self, timeout):
        self._record_send(bridge.BATTERY_QUERY, timeout)

    def send_anc_query(self, timeout):
        self._record_send(bridge.ANC_QUERY, timeout)

    def send_anc_write(self, mode, timeout):
        self._record_send(bridge._ANC_WRITE_FRAMES[mode], timeout)

    def receive_frame(self, timeout):
        index = len(self.receive_timeouts)
        self.events.append("receive")
        self.receive_timeouts.append(timeout)
        if self.clock is not None and index < len(self.receive_advances):
            self.clock.advance(self.receive_advances[index])
        if not self.responses:
            raise bridge.BridgeError("socket_closed")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        if self.closed:
            return
        self.events.append("close")
        self.close_calls += 1
        self.closed = True


class RecordingFactory:
    def __init__(self, transport):
        self.transport = transport
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.transport


class FakeSocket:
    def __init__(
        self,
        reported_security=b"\x02\x00",
        set_error=None,
        get_error=None,
        connect_error=None,
        recv_chunks=(),
        startup_frame=STARTUP_FRAME,
    ):
        self.reported_security = reported_security
        self.set_error = set_error
        self.get_error = get_error
        self.connect_error = connect_error
        self.recv_chunks = ([] if startup_frame is None else [startup_frame]) + list(
            recv_chunks
        )
        self.events = []
        self.closed = False

    def settimeout(self, timeout):
        self.events.append(("timeout", timeout))

    def setsockopt(self, level, option, value):
        self.events.append(("set_security", level, option, value))
        if self.set_error is not None:
            raise self.set_error

    def getsockopt(self, level, option, size):
        self.events.append(("get_security", level, option, size))
        if self.get_error is not None:
            raise self.get_error
        return self.reported_security

    def connect(self, target):
        self.events.append(("connect", target))
        if self.connect_error is not None:
            raise self.connect_error

    def sendall(self, payload):
        self.events.append(("sendall", payload))

    def recv(self, size):
        self.events.append(("recv", size))
        if not self.recv_chunks:
            return b""
        return self.recv_chunks.pop(0)

    def close(self):
        self.events.append("close")
        self.closed = True


class RfcommTransportPolicyTests(unittest.TestCase):
    def socket_constants(self):
        return (
            mock.patch.object(bridge.socket, "AF_BLUETOOTH", 31, create=True),
            mock.patch.object(bridge.socket, "BTPROTO_RFCOMM", 3, create=True),
            mock.patch.object(bridge.socket, "SOL_BLUETOOTH", 274, create=True),
            mock.patch.object(bridge.socket, "BT_SECURITY", 4, create=True),
        )

    def test_socket_family_type_protocol_channel_and_security_are_fixed(self):
        fake_socket = FakeSocket()
        construction = []

        def factory(*arguments):
            construction.append(arguments)
            return fake_socket

        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(socket_factory=factory)
            transport.connect(ADDRESS, 3.0)
            transport.close()

        self.assertEqual(construction, [(31, socket.SOCK_STREAM, 3)])
        security_set = next(event for event in fake_socket.events if isinstance(event, tuple) and event[0] == "set_security")
        self.assertEqual(security_set, ("set_security", 274, 4, b"\x02\x00"))
        self.assertLess(fake_socket.events.index(security_set), fake_socket.events.index(("connect", (ADDRESS, 1))))
        self.assertIn(("get_security", 274, 4, 2), fake_socket.events)
        self.assertTrue(fake_socket.closed)

    def test_connect_consumes_the_exact_empty_startup_frame_before_queries(self):
        fake_socket = FakeSocket(recv_chunks=[identity()])
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
            transport.connect(ADDRESS, 3.0)
            response = transport.receive_frame(2.0)
            transport.close()

        self.assertEqual((response["service"], response["command"]), (1, 7))
        self.assertEqual(response["tlvs"], bridge.parse_frame(identity())["tlvs"])

    def test_connect_rejects_missing_malformed_or_nonexact_startup_frames(self):
        damaged = bytearray(STARTUP_FRAME)
        damaged[-1] ^= 1
        cases = (
            (None, "socket_closed"),
            (bytes(damaged), "invalid_frame"),
            (identity(), "unexpected_response"),
            (frame(1, 6, [(1, b"\x00")]), "unexpected_response"),
            (STARTUP_FRAME + identity(), "unexpected_response"),
        )
        for startup_frame, expected in cases:
            fake_socket = FakeSocket(startup_frame=startup_frame)
            patches = self.socket_constants()
            with self.subTest(expected=expected):
                with patches[0], patches[1], patches[2], patches[3]:
                    transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
                    try:
                        with self.assertRaisesRegex(bridge.BridgeError, expected):
                            transport.connect(ADDRESS, 3.0)
                    finally:
                        transport.close()

    def test_security_level_above_medium_is_accepted_without_alternate_call(self):
        fake_socket = FakeSocket(reported_security=b"\x03\x00")
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
            transport.connect(ADDRESS, 3.0)
            transport.close()
        sets = [event for event in fake_socket.events if isinstance(event, tuple) and event[0] == "set_security"]
        self.assertEqual(sets, [("set_security", 274, 4, b"\x02\x00")])

    def test_transport_exposes_only_fixed_query_and_validated_mode_sends(self):
        fake_socket = FakeSocket()
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(
                socket_factory=lambda *_: fake_socket,
                readiness=no_prior_input,
            )
            transport.connect(ADDRESS, 3.0)
            transport.send_device_info_query(1.0)
            transport.send_battery_query(1.0)
            transport.send_anc_query(1.0)
            transport.send_anc_write("off", 1.0)
            transport.send_anc_write("anc", 1.0)
            transport.send_anc_write("awareness", 1.0)
            with self.assertRaisesRegex(bridge.BridgeError, "invalid_request"):
                transport.send_anc_write("transparent", 1.0)
            for mode in (["anc"], type("Mode", (str,), {})("anc")):
                with self.assertRaisesRegex(bridge.BridgeError, "invalid_request"):
                    transport.send_anc_write(mode, 1.0)
            transport.close()
        sent = [event[1] for event in fake_socket.events if isinstance(event, tuple) and event[0] == "sendall"]
        self.assertEqual(sent, list(bridge.RETAINED_FRAMES))
        self.assertFalse(hasattr(transport, "send"))

    def test_preloaded_complete_or_partial_successor_frame_faults_transaction(self):
        preloaded_chunks = (
            identity() + CAPTURED_ANC["off"] + CAPTURED_ANC["anc"],
            identity() + b"\x5A",
        )
        for chunk in preloaded_chunks:
            fake_socket = FakeSocket(recv_chunks=[chunk])
            patches = self.socket_constants()
            with self.subTest(chunk=chunk.hex()), patches[0], patches[1], patches[2], patches[3]:
                transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
                transport.connect(ADDRESS, 3.0)
                with self.assertRaisesRegex(bridge.BridgeError, "unexpected_response"):
                    transport.receive_frame(2.0)
                transport.close()

    def test_segmented_queued_successor_faults_before_next_send(self):
        for queued_successor in (CAPTURED_BATTERY, b"\x5A"):
            fake_socket = FakeSocket(recv_chunks=[identity(), queued_successor])
            readiness_results = iter((False, True))

            def readiness(active_socket):
                self.assertIs(active_socket, fake_socket)
                fake_socket.events.append("readiness")
                return next(readiness_results)

            patches = self.socket_constants()
            with self.subTest(successor=queued_successor.hex()), patches[0], patches[1], patches[2], patches[3]:
                transport = bridge.RfcommTransport(
                    socket_factory=lambda *_: fake_socket,
                    readiness=readiness,
                )
                controller = bridge.TransactionController(lambda: transport)
                with self.assertRaisesRegex(bridge.BridgeError, "unexpected_response"):
                    controller.refresh(ADDRESS)

            protocol_events = [
                event
                for event in fake_socket.events
                if event in ("readiness", "close")
                or (isinstance(event, tuple) and event[0] in ("connect", "sendall", "recv"))
            ]
            self.assertEqual(protocol_events[0], ("connect", (ADDRESS, bridge.RFCOMM_CHANNEL)))
            sends = [
                event[1]
                for event in protocol_events
                if isinstance(event, tuple) and event[0] == "sendall"
            ]
            self.assertEqual(
                sends,
                [bridge.DEVICE_INFO_QUERY],
            )
            self.assertEqual(protocol_events[-1], "close")

    def test_ready_empty_control_frame_is_consumed_before_next_send(self):
        fake_socket = FakeSocket(
            recv_chunks=[
                identity(),
                STARTUP_FRAME,
                CAPTURED_BATTERY,
                CAPTURED_ANC["off"],
            ]
        )
        readiness_results = iter((False, True, False, False))

        def readiness(active_socket):
            self.assertIs(active_socket, fake_socket)
            return next(readiness_results)

        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(
                socket_factory=lambda *_: fake_socket,
                readiness=readiness,
            )
            result = bridge.TransactionController(lambda: transport).refresh(ADDRESS)

        self.assertTrue(result["readVerified"])
        sent = [
            event[1]
            for event in fake_socket.events
            if isinstance(event, tuple) and event[0] == "sendall"
        ]
        self.assertEqual(sent, [bridge.DEVICE_INFO_QUERY, bridge.BATTERY_QUERY, bridge.ANC_QUERY])

    def test_no_sequence_protocol_cannot_prove_causality_after_send_boundary(self):
        fake_socket = FakeSocket(
            recv_chunks=[identity(), CAPTURED_BATTERY, CAPTURED_ANC["off"]]
        )
        boundary_calls = []

        def readiness(active_socket):
            boundary_calls.append(active_socket)
            return False

        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(
                socket_factory=lambda *_: fake_socket,
                readiness=readiness,
            )
            result = bridge.TransactionController(lambda: transport).refresh(ADDRESS)

        # With no sequence field, matching input that becomes visible only
        # after each boundary remains indistinguishable from a causal reply.
        self.assertTrue(result["readVerified"])
        self.assertEqual(boundary_calls, [fake_socket, fake_socket, fake_socket])

    def test_exact_empty_control_frames_are_consumed_around_expected_replies(self):
        fake_socket = FakeSocket(
            recv_chunks=[
                STARTUP_FRAME,
                identity(),
                CAPTURED_BATTERY + STARTUP_FRAME,
                STARTUP_FRAME,
                CAPTURED_ANC["anc"],
            ]
        )
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(
                socket_factory=lambda *_: fake_socket,
                readiness=no_prior_input,
            )
            result = bridge.TransactionController(lambda: transport).refresh(ADDRESS)

        self.assertTrue(result["readVerified"])
        self.assertEqual(result["battery"]["left"], 100)
        self.assertEqual(result["anc"]["mode"], "anc")
        sent = [
            event[1]
            for event in fake_socket.events
            if isinstance(event, tuple) and event[0] == "sendall"
        ]
        self.assertEqual(sent, [bridge.DEVICE_INFO_QUERY, bridge.BATTERY_QUERY, bridge.ANC_QUERY])

    def test_duplicate_empty_control_frames_fault_without_resending(self):
        fake_socket = FakeSocket(recv_chunks=[STARTUP_FRAME + STARTUP_FRAME, identity()])
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(
                socket_factory=lambda *_: fake_socket,
                readiness=no_prior_input,
            )
            with self.assertRaisesRegex(bridge.BridgeError, "unexpected_response"):
                bridge.TransactionController(lambda: transport).refresh(ADDRESS)

        sent = [
            event[1]
            for event in fake_socket.events
            if isinstance(event, tuple) and event[0] == "sendall"
        ]
        self.assertEqual(sent, [bridge.DEVICE_INFO_QUERY])

    def test_missing_security_constants_prevent_socket_construction_and_connect(self):
        constructed = []
        with mock.patch.object(bridge.socket, "AF_BLUETOOTH", 31, create=True), mock.patch.object(
            bridge.socket, "BTPROTO_RFCOMM", 3, create=True
        ), mock.patch.object(bridge.socket, "SOL_BLUETOOTH", None, create=True), mock.patch.object(
            bridge.socket, "BT_SECURITY", 4, create=True
        ):
            transport = bridge.RfcommTransport(socket_factory=lambda *_: constructed.append(True))
            with self.assertRaisesRegex(bridge.BridgeError, "security_failed"):
                transport.connect(ADDRESS, 3.0)
        self.assertEqual(constructed, [])

    def test_every_security_failure_prevents_connect(self):
        cases = (
            FakeSocket(set_error=OSError("set failed")),
            FakeSocket(get_error=OSError("get failed")),
            FakeSocket(reported_security=b"\x02"),
            FakeSocket(reported_security=b"\x01\x00"),
        )
        for fake_socket in cases:
            patches = self.socket_constants()
            with self.subTest(events=fake_socket.events), patches[0], patches[1], patches[2], patches[3]:
                transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
                try:
                    with self.assertRaisesRegex(bridge.BridgeError, "security_failed"):
                        transport.connect(ADDRESS, 3.0)
                finally:
                    transport.close()
                self.assertFalse(any(isinstance(event, tuple) and event[0] == "connect" for event in fake_socket.events))
                self.assertTrue(fake_socket.closed)

    def test_missing_bluetooth_family_is_transport_unsupported(self):
        with mock.patch.object(bridge.socket, "AF_BLUETOOTH", None, create=True):
            with self.assertRaisesRegex(bridge.BridgeError, "transport_unsupported"):
                bridge.RfcommTransport(socket_factory=lambda *_: self.fail("socket created")).connect(ADDRESS, 3.0)

    def test_closed_transport_cannot_create_or_reopen_a_socket(self):
        constructions = []
        patches = self.socket_constants()
        with patches[0], patches[1], patches[2], patches[3]:
            transport = bridge.RfcommTransport(socket_factory=lambda *_: constructions.append(True))
            transport.close()
            with self.assertRaisesRegex(bridge.BridgeError, "socket_closed"):
                transport.connect(ADDRESS, 3.0)
        self.assertEqual(constructions, [])

    def test_connect_busy_and_refused_map_without_retry(self):
        for error, expected in (
            (OSError(errno.EBUSY, "busy"), "transport_busy"),
            (OSError(errno.ECONNREFUSED, "refused"), "connect_failed"),
            (OSError(errno.ETIMEDOUT, "timed out"), "timeout"),
        ):
            fake_socket = FakeSocket(connect_error=error)
            patches = self.socket_constants()
            with self.subTest(expected=expected), patches[0], patches[1], patches[2], patches[3]:
                transport = bridge.RfcommTransport(socket_factory=lambda *_: fake_socket)
                try:
                    with self.assertRaisesRegex(bridge.BridgeError, expected):
                        transport.connect(ADDRESS, 3.0)
                finally:
                    transport.close()
                self.assertEqual(sum(event == ("connect", (ADDRESS, 1)) for event in fake_socket.events), 1)


class RefreshTransactionTests(unittest.TestCase):
    def controller(self, transport, clock=None):
        factory = RecordingFactory(transport)
        return bridge.TransactionController(factory, clock=clock), factory

    def test_refresh_uses_one_socket_and_exact_serial_order(self):
        clock = FakeClock()
        transport = ScriptedTransport([identity(), CAPTURED_BATTERY, CAPTURED_ANC["anc"]], clock=clock)
        controller, factory = self.controller(transport, clock)
        result = controller.refresh(ADDRESS)

        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.connect_calls, [(ADDRESS, 3.0)])
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY, bridge.BATTERY_QUERY, bridge.ANC_QUERY])
        self.assertEqual(
            transport.events,
            [
                "connect",
                ("send", bridge.DEVICE_INFO_QUERY),
                "receive",
                ("send", bridge.BATTERY_QUERY),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                "close",
            ],
        )
        self.assertEqual(result["battery"]["left"], 100)
        self.assertEqual(result["anc"]["mode"], "anc")
        self.assertTrue(result["readVerified"])
        self.assertEqual(transport.close_calls, 1)
        self.assertIsNone(controller._active_transport)

    def test_identity_failure_prevents_features_and_writes(self):
        transport = ScriptedTransport([identity("000163")])
        controller, factory = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "identity_mismatch"):
            controller.refresh(ADDRESS)
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY])
        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.close_calls, 1)

    def test_valid_shape_crc_connect_and_address_cannot_replace_identity(self):
        for first_response in (CAPTURED_BATTERY, CAPTURED_ANC["off"]):
            transport = ScriptedTransport([first_response])
            controller, _ = self.controller(transport)
            with self.subTest(first_response=first_response.hex()):
                with self.assertRaisesRegex(bridge.BridgeError, "unexpected_response"):
                    controller.refresh(ADDRESS)
                self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY])
                self.assertEqual(transport.close_calls, 1)

    def test_identity_plus_valid_anc_admits_partial_result(self):
        transport = ScriptedTransport([identity(), INVALID_BATTERY_SHAPE, CAPTURED_ANC["awareness"]])
        controller, _ = self.controller(transport)
        result = controller.refresh(ADDRESS)
        self.assertIsNone(result["battery"])
        self.assertEqual(result["batteryError"], "battery_invalid")
        self.assertEqual(result["anc"]["mode"], "awareness")
        self.assertIsNone(result["ancError"])

    def test_identity_plus_valid_battery_admits_partial_result(self):
        transport = ScriptedTransport([identity(), CAPTURED_BATTERY, INVALID_ANC_SHAPE])
        controller, _ = self.controller(transport)
        result = controller.refresh(ADDRESS)
        self.assertEqual(result["battery"]["case"], 85)
        self.assertIsNone(result["anc"])
        self.assertEqual(result["ancError"], "anc_invalid")

    def test_no_pro5_shape_fails_read_verification(self):
        transport = ScriptedTransport([identity(), INVALID_BATTERY_SHAPE, INVALID_ANC_SHAPE])
        controller, _ = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "anc_invalid"):
            controller.refresh(ADDRESS)
        self.assertEqual(transport.close_calls, 1)

    def test_fatal_battery_frame_fault_stops_before_anc(self):
        damaged = bytearray(CAPTURED_BATTERY)
        damaged[-1] ^= 1
        transport = ScriptedTransport([identity(), bytes(damaged), CAPTURED_ANC["off"]])
        controller, _ = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            controller.refresh(ADDRESS)
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY, bridge.BATTERY_QUERY])

    def test_valid_battery_is_retained_when_later_anc_transport_fails(self):
        transport = ScriptedTransport([identity(), CAPTURED_BATTERY, bridge.BridgeError("timeout")])
        controller, _ = self.controller(transport)
        result = controller.refresh(ADDRESS)
        self.assertEqual(result["battery"]["left"], 100)
        self.assertIsNone(result["anc"])
        self.assertEqual(result["ancError"], "timeout")
        self.assertEqual(transport.close_calls, 1)


class AncTransactionTests(unittest.TestCase):
    def controller(self, transport, clock=None):
        factory = RecordingFactory(transport)
        return bridge.TransactionController(factory, clock=clock), factory

    def test_same_socket_identity_and_extended_anc_gate_precede_write(self):
        transport = ScriptedTransport([identity(), INVALID_ANC_SHAPE])
        controller, _ = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "anc_invalid"):
            controller.set_anc(ADDRESS, "anc")
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY, bridge.ANC_QUERY])
        self.assertFalse(any(item in bridge._ANC_WRITE_FRAMES.values() for item in transport.sent))
        self.assertEqual(transport.close_calls, 1)

    def test_mode_requires_exact_str_before_membership_or_transport_creation(self):
        class Mode(str):
            pass

        for mode in (["anc"], {"anc": True}, Mode("anc")):
            factory = mock.Mock(side_effect=AssertionError("transport created"))
            controller = bridge.TransactionController(factory)
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(bridge.BridgeError, "invalid_request"):
                    controller.set_anc(ADDRESS, mode)
                factory.assert_not_called()

    def test_each_mode_uses_exactly_its_retained_write_and_matching_readback(self):
        initial_modes = {"off": "anc", "anc": "off", "awareness": "off"}
        expected_writes = {
            "off": bridge.SET_ANC_OFF,
            "anc": bridge.SET_ANC_ON,
            "awareness": bridge.SET_ANC_AWARENESS,
        }
        for requested, initial in initial_modes.items():
            transport = ScriptedTransport(
                [
                    identity(),
                    CAPTURED_ANC[initial],
                    CAPTURED_ANC_WRITE_ACK,
                    CAPTURED_ANC[requested],
                ]
            )
            controller, factory = self.controller(transport)
            with self.subTest(requested=requested):
                result = controller.set_anc(ADDRESS, requested)
                self.assertEqual(
                    transport.sent,
                    [bridge.DEVICE_INFO_QUERY, bridge.ANC_QUERY, expected_writes[requested], bridge.ANC_QUERY],
                )
                self.assertTrue(result["success"])
                self.assertTrue(result["writePerformed"])
                self.assertEqual(result["anc"]["mode"], requested)
                self.assertEqual(factory.calls, 1)
                self.assertEqual(transport.close_calls, 1)

    def test_write_ack_is_consumed_before_matching_readback(self):
        transport = ScriptedTransport(
            [
                identity(),
                CAPTURED_ANC["off"],
                CAPTURED_ANC_WRITE_ACK,
                CAPTURED_ANC["anc"],
            ]
        )
        controller, _ = self.controller(transport)

        result = controller.set_anc(ADDRESS, "anc")

        self.assertTrue(result["success"])
        self.assertEqual(result["anc"]["mode"], "anc")
        self.assertEqual(
            transport.events,
            [
                "connect",
                ("send", bridge.DEVICE_INFO_QUERY),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                ("send", bridge.SET_ANC_ON),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                "close",
            ],
        )

    def test_already_active_mode_sends_no_write_or_readback_query(self):
        transport = ScriptedTransport([identity(), CAPTURED_ANC["anc"]])
        controller, _ = self.controller(transport)
        result = controller.set_anc(ADDRESS, "anc")
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY, bridge.ANC_QUERY])
        self.assertFalse(result["writePerformed"])
        self.assertEqual(result["anc"]["mode"], "anc")

    def test_write_send_failure_is_not_replayed(self):
        transport = ScriptedTransport(
            [identity(), CAPTURED_ANC["off"]],
            send_errors={2: bridge.BridgeError("socket_closed")},
        )
        controller, factory = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "anc_send_failed"):
            controller.set_anc(ADDRESS, "anc")
        self.assertEqual(transport.sent.count(bridge.SET_ANC_ON), 1)
        self.assertEqual(transport.sent.count(bridge.ANC_QUERY), 1)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(
            transport.events,
            [
                "connect",
                ("send", bridge.DEVICE_INFO_QUERY),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                ("send", bridge.SET_ANC_ON),
                "close",
            ],
        )

    def test_missing_malformed_or_rejected_write_acks_never_query_readback(self):
        damaged = bytearray(CAPTURED_ANC_WRITE_ACK)
        damaged[-1] ^= 1
        ack_failures = (
            bridge.BridgeError("socket_closed"),
            bytes(damaged),
            bridge.BridgeError("timeout"),
            frame(0x2B, 0x04, [(0x02, b"\x01")]),
            CAPTURED_ANC["anc"],
        )
        for failure in ack_failures:
            transport = ScriptedTransport([identity(), CAPTURED_ANC["off"], failure])
            controller, factory = self.controller(transport)
            with self.subTest(failure=repr(failure)):
                with self.assertRaisesRegex(bridge.BridgeError, "anc_send_failed"):
                    controller.set_anc(ADDRESS, "anc")
                self.assertEqual(transport.sent.count(bridge.SET_ANC_ON), 1)
                self.assertEqual(transport.sent.count(bridge.ANC_QUERY), 1)
                self.assertEqual(factory.calls, 1)
                self.assertEqual(transport.close_calls, 1)

    def test_missing_malformed_and_timed_out_readbacks_never_replay(self):
        damaged = bytearray(CAPTURED_ANC["anc"])
        damaged[-1] ^= 1
        readback_failures = (
            bridge.BridgeError("socket_closed"),
            bytes(damaged),
            bridge.BridgeError("timeout"),
            INVALID_ANC_SHAPE,
        )
        for failure in readback_failures:
            transport = ScriptedTransport(
                [identity(), CAPTURED_ANC["off"], CAPTURED_ANC_WRITE_ACK, failure]
            )
            controller, factory = self.controller(transport)
            with self.subTest(failure=repr(failure)):
                with self.assertRaisesRegex(bridge.BridgeError, "anc_readback_failed"):
                    controller.set_anc(ADDRESS, "anc")
                self.assertEqual(transport.sent.count(bridge.SET_ANC_ON), 1)
                self.assertEqual(transport.sent.count(bridge.ANC_QUERY), 2)
                self.assertEqual(factory.calls, 1)
                self.assertEqual(transport.close_calls, 1)
                self.assertEqual(
                    transport.events,
                    [
                        "connect",
                        ("send", bridge.DEVICE_INFO_QUERY),
                        "receive",
                        ("send", bridge.ANC_QUERY),
                        "receive",
                        ("send", bridge.SET_ANC_ON),
                        "receive",
                        ("send", bridge.ANC_QUERY),
                        "receive",
                        "close",
                    ],
                )

    def test_valid_mismatching_readback_reports_observed_mode_without_replay(self):
        transport = ScriptedTransport(
            [
                identity(),
                CAPTURED_ANC["off"],
                CAPTURED_ANC_WRITE_ACK,
                CAPTURED_ANC["awareness"],
            ]
        )
        controller, _ = self.controller(transport)
        with self.assertRaises(bridge.BridgeError) as raised:
            controller.set_anc(ADDRESS, "anc")
        self.assertEqual(raised.exception.code, "anc_readback_mismatch")
        self.assertEqual(raised.exception.details["observedMode"], "awareness")
        self.assertEqual(transport.sent.count(bridge.SET_ANC_ON), 1)
        self.assertEqual(transport.sent.count(bridge.ANC_QUERY), 2)
        self.assertEqual(
            transport.events,
            [
                "connect",
                ("send", bridge.DEVICE_INFO_QUERY),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                ("send", bridge.SET_ANC_ON),
                "receive",
                ("send", bridge.ANC_QUERY),
                "receive",
                "close",
            ],
        )

    def test_identity_failure_prevents_every_anc_write(self):
        transport = ScriptedTransport([identity("000163")])
        controller, _ = self.controller(transport)
        with self.assertRaisesRegex(bridge.BridgeError, "identity_mismatch"):
            controller.set_anc(ADDRESS, "awareness")
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY])


class DeadlineAndClosureTests(unittest.TestCase):
    def controller(self, transport, clock=None):
        factory = RecordingFactory(transport)
        return bridge.TransactionController(factory, clock=clock), factory

    def test_connect_deadline_faults_once_and_closes_once(self):
        clock = FakeClock()
        transport = ScriptedTransport([identity()], clock=clock, connect_advance=3.01)
        controller, factory = self.controller(transport, clock)
        with self.assertRaisesRegex(bridge.BridgeError, "timeout"):
            controller.refresh(ADDRESS)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.connect_calls, [(ADDRESS, 3.0)])
        self.assertEqual(transport.close_calls, 1)
        self.assertEqual(transport.sent, [])

    def test_default_transaction_clocks_use_linux_boottime(self):
        with mock.patch.object(bridge.time, "clock_gettime", return_value=123.5) as clock_gettime:
            controller = bridge.TransactionController(lambda: None)
            transport = bridge.RfcommTransport(readiness=no_prior_input)
            self.assertEqual(controller._clock(), 123.5)
            self.assertEqual(transport._clock(), 123.5)
        self.assertEqual(
            clock_gettime.call_args_list,
            [mock.call(bridge.time.CLOCK_BOOTTIME), mock.call(bridge.time.CLOCK_BOOTTIME)],
        )

    def test_each_response_deadline_is_two_seconds(self):
        clock = FakeClock()
        transport = ScriptedTransport([identity()], clock=clock, receive_advances=[2.01])
        controller, _ = self.controller(transport, clock)
        with self.assertRaisesRegex(bridge.BridgeError, "timeout"):
            controller.refresh(ADDRESS)
        self.assertEqual(transport.receive_timeouts, [2.0])
        self.assertEqual(transport.close_calls, 1)

    def test_total_deadline_includes_sends_and_closes_once(self):
        clock = FakeClock()
        transport = ScriptedTransport([identity()], clock=clock, send_advances=[10.01])
        controller, factory = self.controller(transport, clock)
        with self.assertRaisesRegex(bridge.BridgeError, "timeout"):
            controller.refresh(ADDRESS)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.close_calls, 1)
        self.assertEqual(transport.sent, [bridge.DEVICE_INFO_QUERY])

    def test_eof_busy_unexpected_bad_frame_and_disconnect_do_not_retry(self):
        damaged = bytearray(identity())
        damaged[-1] ^= 1
        query_failure_events = [
            "connect",
            ("send", bridge.DEVICE_INFO_QUERY),
            "receive",
            "close",
        ]
        cases = (
            (ScriptedTransport([]), "socket_closed", query_failure_events),
            (
                ScriptedTransport([], connect_error=bridge.BridgeError("transport_busy")),
                "transport_busy",
                ["connect", "close"],
            ),
            (ScriptedTransport([CAPTURED_ANC["off"]]), "unexpected_response", query_failure_events),
            (ScriptedTransport([bytes(damaged)]), "invalid_frame", query_failure_events),
            (
                ScriptedTransport([bridge.BridgeError("socket_closed")]),
                "socket_closed",
                query_failure_events,
            ),
        )
        for transport, expected, expected_events in cases:
            controller, factory = self.controller(transport)
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(bridge.BridgeError, expected):
                    controller.refresh(ADDRESS)
                self.assertEqual(factory.calls, 1)
                self.assertEqual(transport.close_calls, 1)
                self.assertEqual(transport.events, expected_events)
                self.assertIsNone(controller._active_transport)

    def test_invalid_address_fails_before_transport_creation(self):
        factory = mock.Mock(side_effect=AssertionError("transport must not be created"))
        controller = bridge.TransactionController(factory)
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_address"):
            controller.refresh("aa:bb:cc:dd:ee:ff")
        factory.assert_not_called()

    def test_concurrent_controller_call_is_busy_and_not_queued(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingTransport(ScriptedTransport):
            def receive_frame(self, timeout):
                if not started.is_set():
                    started.set()
                    release.wait(2.0)
                return super().receive_frame(timeout)

        transport = BlockingTransport([identity(), CAPTURED_BATTERY, CAPTURED_ANC["off"]])
        controller, factory = self.controller(transport)
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(controller.refresh(ADDRESS)))
        worker.start()
        self.assertTrue(started.wait(2.0))
        with self.assertRaisesRegex(bridge.BridgeError, "busy"):
            controller.refresh(ADDRESS)
        release.set()
        worker.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.close_calls, 1)

    def test_cancel_closes_active_transport_once(self):
        started = threading.Event()
        released = threading.Event()

        class CancelTransport(ScriptedTransport):
            def receive_frame(self, timeout):
                started.set()
                released.wait(2.0)
                raise bridge.BridgeError("socket_closed")

            def close(self):
                super().close()
                released.set()

        transport = CancelTransport()
        controller, _ = self.controller(transport)
        errors = []

        def run():
            try:
                controller.refresh(ADDRESS)
            except bridge.BridgeError as error:
                errors.append(error.code)

        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(started.wait(2.0))
        controller.cancel()
        worker.join(2.0)
        self.assertEqual(errors, ["socket_closed"])
        self.assertEqual(transport.close_calls, 1)
        self.assertIsNone(controller._active_transport)

    def test_cancel_before_controller_entry_is_consumed_without_transport(self):
        transport = ScriptedTransport([identity(), CAPTURED_BATTERY, CAPTURED_ANC["off"]])
        controller, factory = self.controller(transport)
        controller.cancel()
        with self.assertRaisesRegex(bridge.BridgeError, "socket_closed"):
            controller.refresh(ADDRESS)
        self.assertEqual(factory.calls, 0)
        result = controller.refresh(ADDRESS)
        self.assertTrue(result["readVerified"])
        self.assertEqual(factory.calls, 1)

    def test_cancel_during_factory_creation_prevents_connect_and_send(self):
        factory_started = threading.Event()
        release_factory = threading.Event()
        transport = ScriptedTransport()

        class BlockingFactory:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                factory_started.set()
                release_factory.wait(2.0)
                return transport

        factory = BlockingFactory()
        controller = bridge.TransactionController(factory)
        errors = []

        def run():
            try:
                controller.refresh(ADDRESS)
            except bridge.BridgeError as error:
                errors.append(error.code)

        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(factory_started.wait(2.0))
        controller.cancel()
        release_factory.set()
        worker.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, ["socket_closed"])
        self.assertEqual(factory.calls, 1)
        self.assertEqual(transport.connect_calls, [])
        self.assertEqual(transport.sent, [])
        self.assertEqual(transport.close_calls, 1)

    def test_cancel_after_registration_but_before_connect_prevents_contact(self):
        clock_entered = threading.Event()
        release_clock = threading.Event()

        class BlockingClock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    clock_entered.set()
                    release_clock.wait(2.0)
                return 100.0

        clock = BlockingClock()
        transport = ScriptedTransport()
        controller, _ = self.controller(transport, clock)
        errors = []

        def run():
            try:
                controller.refresh(ADDRESS)
            except bridge.BridgeError as error:
                errors.append(error.code)

        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(clock_entered.wait(2.0))
        controller.cancel()
        release_clock.set()
        worker.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, ["socket_closed"])
        self.assertEqual(transport.connect_calls, [])
        self.assertEqual(transport.sent, [])
        self.assertEqual(transport.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
