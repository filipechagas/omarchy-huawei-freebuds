import ast
import copy
import errno
import io
import json
import os
import queue
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from bridge import freebuds_bridge as bridge


ADDRESS = "AA:BB:CC:DD:EE:FF"
OTHER_ADDRESS = "11:22:33:44:55:66"


def request(request_id, method, generation=4, **fields):
    value = {
        "v": 1,
        "type": "request",
        "id": request_id,
        "generation": generation,
        "method": method,
    }
    value.update(fields)
    return value


def encoded_request(request_id, method, generation=4, **fields):
    return json.dumps(request(request_id, method, generation, **fields), separators=(",", ":")).encode() + b"\n"


def parse_lines(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


class FakeController:
    def __init__(self, refresh_result=None, anc_result=None, refresh_error=None, anc_error=None):
        self.refresh_result = refresh_result or {
            "identityVerified": True,
            "readVerified": True,
            "battery": {"left": 100, "right": 100, "case": 85, "observedAt": 100.0},
            "batteryError": None,
            "anc": {"mode": "off", "observedAt": 100.0},
            "ancError": None,
        }
        self.anc_result = anc_result or {
            "identityVerified": True,
            "success": True,
            "anc": {"mode": "anc", "observedAt": 101.0},
            "writePerformed": True,
        }
        self.refresh_error = refresh_error
        self.anc_error = anc_error
        self.refresh_calls = []
        self.anc_calls = []
        self.cancel_calls = 0

    def refresh(self, address):
        self.refresh_calls.append(address)
        if self.refresh_error is not None:
            raise self.refresh_error
        return copy.deepcopy(self.refresh_result)

    def set_anc(self, address, mode):
        self.anc_calls.append((address, mode))
        if self.anc_error is not None:
            raise self.anc_error
        result = copy.deepcopy(self.anc_result)
        result["anc"]["mode"] = mode
        return result

    def cancel(self):
        self.cancel_calls += 1


class QueueInput:
    def __init__(self):
        self._queue = queue.Queue()
        self._pending = b""

    def feed(self, line):
        self._queue.put(line)

    def close(self):
        self._queue.put(None)

    def readline(self, limit):
        if not self._pending:
            item = self._queue.get()
            if item is None:
                return b""
            self._pending = item
        result = self._pending[:limit]
        self._pending = self._pending[limit:]
        return result


class RecordingStream:
    def __init__(self):
        self._buffer = bytearray()
        self._condition = threading.Condition()

    def write(self, value):
        with self._condition:
            self._buffer.extend(value)
            self._condition.notify_all()
        return len(value)

    def flush(self):
        pass

    def wait_for_lines(self, count):
        with self._condition:
            return self._condition.wait_for(lambda: self._buffer.count(b"\n") >= count, timeout=2.0)

    def wait_for_type(self, message_type):
        def contains_type():
            return any(
                json.loads(line).get("type") == message_type
                for line in bytes(self._buffer).splitlines()
            )

        with self._condition:
            return self._condition.wait_for(contains_type, timeout=2.0)

    def getvalue(self):
        with self._condition:
            return bytes(self._buffer)


def serve_queued(process, data):
    input_stream = QueueInput()
    output = RecordingStream()
    errors = RecordingStream()
    outcome = []

    def run():
        try:
            outcome.append(("return", process.serve(input_stream, output, errors)))
        except BaseException as error:
            outcome.append(("error", error))

    server = threading.Thread(target=run)
    server.start()
    if not output.wait_for_type("hello"):
        raise AssertionError("bridge did not emit hello")
    for line in data.splitlines(keepends=True):
        expected_lines = output.getvalue().count(b"\n") + 1
        input_stream.feed(line)
        if not output.wait_for_lines(expected_lines):
            raise AssertionError("bridge did not emit a terminal response")
    input_stream.close()
    server.join(2.0)
    if server.is_alive():
        raise AssertionError("bridge did not stop")
    if outcome and outcome[0][0] == "error":
        raise outcome[0][1]
    return outcome[0][1], output, errors


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(
            self.temporary.name,
            "omarchy",
            "io.github.filipechagas.freebuds.json",
        )
        self.store = bridge.ConfigStore(self.path)

    def write_raw(self, raw, mode=0o600):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        with open(self.path, "wb") as config_file:
            config_file.write(raw)
        os.chmod(self.path, mode)

    def test_default_config_path_uses_xdg_then_home_fallback(self):
        self.assertEqual(
            bridge.default_config_path({"XDG_CONFIG_HOME": "/xdg", "HOME": "/home/user"}),
            "/xdg/omarchy/io.github.filipechagas.freebuds.json",
        )
        self.assertEqual(
            bridge.default_config_path({"XDG_CONFIG_HOME": "", "HOME": "/home/user"}),
            "/home/user/.config/omarchy/io.github.filipechagas.freebuds.json",
        )

    def test_missing_config_is_no_selection_not_an_error(self):
        self.assertEqual(self.store.load(), (None, None))

    def test_save_is_exact_schema_mode_0600_and_parent_mode_0700(self):
        self.store.save(ADDRESS)
        self.assertEqual(self.store.load(), (ADDRESS, None))
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.path)).st_mode), 0o700)
        with open(self.path, "rb") as config_file:
            self.assertEqual(
                json.loads(config_file.read()),
                {"schemaVersion": 1, "selectedAddress": ADDRESS},
            )

    def test_every_non_0600_mode_is_invalid(self):
        self.write_raw(json.dumps({"schemaVersion": 1, "selectedAddress": ADDRESS}).encode())
        for mode in (0o000, 0o200, 0o400, 0o640, 0o644, 0o660, 0o666):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.path, mode)
                self.assertEqual(self.store.load(), (None, "config_invalid"))

    def test_invalid_addresses_are_rejected(self):
        invalid = ("aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE", "GG:BB:CC:DD:EE:FF", "", None, 1)
        for address in invalid:
            with self.subTest(address=address):
                self.write_raw(json.dumps({"schemaVersion": 1, "selectedAddress": address}).encode())
                self.assertEqual(self.store.load(), (None, "config_invalid"))

    def test_unknown_schema_unknown_fields_and_missing_values_are_invalid(self):
        values = (
            {"schemaVersion": 2, "selectedAddress": ADDRESS},
            {"schemaVersion": True, "selectedAddress": ADDRESS},
            {"schemaVersion": 1, "selectedAddress": ADDRESS, "name": "FreeBuds"},
            {"schemaVersion": 1},
            {"selectedAddress": ADDRESS},
        )
        for value in values:
            with self.subTest(value=value):
                self.write_raw(json.dumps(value).encode())
                self.assertEqual(self.store.load(), (None, "config_invalid"))

    def test_malformed_duplicate_nonfinite_and_oversized_json_are_invalid(self):
        values = (
            b"{",
            b'{"schemaVersion":1,"schemaVersion":1,"selectedAddress":"AA:BB:CC:DD:EE:FF"}',
            b'{"schemaVersion":NaN,"selectedAddress":"AA:BB:CC:DD:EE:FF"}',
            b"\xff",
            b"{" + b" " * bridge.MAX_JSONL_BYTES + b"}",
            b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
        )
        for raw in values:
            with self.subTest(prefix=raw[:20]):
                self.write_raw(raw)
                self.assertEqual(self.store.load(), (None, "config_invalid"))

    def test_symlink_and_directory_targets_are_invalid(self):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700)
        target = os.path.join(self.temporary.name, "target.json")
        with open(target, "wb") as target_file:
            target_file.write(b"{}")
        os.symlink(target, self.path)
        self.assertEqual(self.store.load(), (None, "config_invalid"))
        os.unlink(self.path)
        os.mkdir(self.path)
        self.assertEqual(self.store.load(), (None, "config_invalid"))

    def test_non_owner_readable_file_is_invalid_without_attempting_read(self):
        self.write_raw(json.dumps({"schemaVersion": 1, "selectedAddress": ADDRESS}).encode(), mode=0o200)
        real_open = bridge.os.open
        with mock.patch.object(bridge.os, "open", wraps=real_open) as opened:
            self.assertEqual(self.store.load(), (None, "config_invalid"))
        target_opens = [
            call for call in opened.call_args_list if call.args[0] == os.path.basename(self.path)
        ]
        self.assertEqual(target_opens, [])

    def test_atomic_replacement_uses_same_directory(self):
        self.store.save(OTHER_ADDRESS)
        original_replace = bridge.os.replace
        replacements = []

        def recording_replace(source, target, **kwargs):
            replacements.append((source, target, kwargs))
            return original_replace(source, target, **kwargs)

        with mock.patch.object(bridge.os, "replace", side_effect=recording_replace):
            self.store.save(ADDRESS)
        self.assertEqual(len(replacements), 1)
        source, target, kwargs = replacements[0]
        self.assertEqual(os.path.dirname(source), "")
        self.assertEqual(target, os.path.basename(self.path))
        self.assertEqual(kwargs["src_dir_fd"], kwargs["dst_dir_fd"])
        self.assertEqual(self.store.load(), (ADDRESS, None))

    def test_each_operation_uses_one_validated_nofollow_parent_descriptor(self):
        real_open = bridge.os.open
        for operation in (
            lambda: self.store.save(ADDRESS),
            self.store.load,
            self.store.clear,
        ):
            with self.subTest(operation=operation), mock.patch.object(
                bridge.os, "open", wraps=real_open
            ) as opened:
                operation()
            parent_calls = [
                call for call in opened.call_args_list if call.args[0] == os.path.dirname(self.path)
            ]
            self.assertEqual(len(parent_calls), 1)
            self.assertTrue(parent_calls[0].args[1] & os.O_NOFOLLOW)
            for call in opened.call_args_list:
                if call in parent_calls:
                    continue
                self.assertEqual(os.path.dirname(call.args[0]), "")
                self.assertIn("dir_fd", call.kwargs)

    def test_load_save_and_clear_take_shared_or_exclusive_directory_flocks(self):
        real_flock = bridge.fcntl.flock
        lock_operations = []

        def recording_flock(descriptor, operation):
            lock_operations.append(operation)
            return real_flock(descriptor, operation)

        with mock.patch.object(bridge.fcntl, "flock", side_effect=recording_flock):
            self.store.save(ADDRESS)
            self.assertEqual(self.store.load(), (ADDRESS, None))
            self.store.clear()
        self.assertEqual(
            [operation & ~bridge.fcntl.LOCK_NB for operation in lock_operations],
            [bridge.fcntl.LOCK_EX, bridge.fcntl.LOCK_SH, bridge.fcntl.LOCK_EX],
        )
        self.assertTrue(all(operation & bridge.fcntl.LOCK_NB for operation in lock_operations))

    def test_config_lock_timeouts_are_boottime_bounded_and_stably_mapped(self):
        self.write_raw(json.dumps({"schemaVersion": 1, "selectedAddress": ADDRESS}).encode())

        class AdvancingClock:
            def __init__(self):
                self.now = 100.0
                self.sleeps = []

            def __call__(self):
                return self.now

            def sleep(self, seconds):
                self.sleeps.append(seconds)
                self.now += seconds

        def contended_flock(_descriptor, operation):
            self.assertTrue(operation & bridge.fcntl.LOCK_NB)
            raise BlockingIOError(errno.EAGAIN, "contended")

        for operation, expected in (
            ("load", (None, "config_invalid")),
            ("save", "config_write_failed"),
            ("clear", "config_write_failed"),
        ):
            clock = AdvancingClock()
            store = bridge.ConfigStore(self.path, clock=clock, sleep=clock.sleep)
            with self.subTest(operation=operation), mock.patch.object(
                bridge, "CONFIG_LOCK_TIMEOUT_SECONDS", 0.03
            ), mock.patch.object(bridge.fcntl, "flock", side_effect=contended_flock):
                if operation == "load":
                    self.assertEqual(store.load(), expected)
                else:
                    with self.assertRaises(bridge.BridgeError) as raised:
                        getattr(store, operation)(ADDRESS) if operation == "save" else store.clear()
                    self.assertEqual(raised.exception.code, expected)
            self.assertGreaterEqual(clock.now, 100.03)
            self.assertLess(clock.now, 100.04)
            self.assertTrue(clock.sleeps)

    def test_default_config_lock_clock_is_linux_boottime(self):
        with mock.patch.object(bridge.time, "clock_gettime", return_value=321.0) as clock_gettime:
            store = bridge.ConfigStore(self.path)
            self.assertEqual(store._clock(), 321.0)
        clock_gettime.assert_called_once_with(bridge.time.CLOCK_BOOTTIME)

    def test_directory_flock_serializes_a_cooperating_bridge_process(self):
        self.store.save(ADDRESS)
        parent = os.path.dirname(self.path)
        descriptor = os.open(
            parent,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        bridge.fcntl.flock(descriptor, bridge.fcntl.LOCK_EX)
        script = (
            "import sys\n"
            "from bridge import freebuds_bridge as bridge\n"
            "print('ready', flush=True)\n"
            "bridge.ConfigStore(sys.argv[1]).save(sys.argv[2])\n"
            "print('saved', flush=True)\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", script, self.path, OTHER_ADDRESS],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(bridge.__file__)),
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        blocked = False
        try:
            self.assertEqual(child.stdout.readline(), b"ready\n")
            try:
                child.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                blocked = True
        finally:
            bridge.fcntl.flock(descriptor, bridge.fcntl.LOCK_UN)
            os.close(descriptor)
        stdout, stderr = child.communicate(timeout=2.0)
        self.assertTrue(blocked)
        self.assertEqual((child.returncode, stdout, stderr), (0, b"saved\n", b""))
        self.assertEqual(self.store.load(), (OTHER_ADDRESS, None))

    def test_injected_atomic_replace_failure_cleans_temporary_file(self):
        with mock.patch.object(bridge.os, "replace", side_effect=OSError("injected write failure")):
            with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
                self.store.save(ADDRESS)
        parent = os.path.dirname(self.path)
        self.assertEqual(os.listdir(parent), [])

    def test_post_replace_symlink_swap_is_rejected_without_chmod_follow(self):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700)
        external = os.path.join(self.temporary.name, "external")
        with open(external, "wb") as external_file:
            external_file.write(b"external")
        os.chmod(external, 0o644)
        original_replace = bridge.os.replace

        def swap_after_replace(source, target, **kwargs):
            original_replace(source, target, **kwargs)
            installed = os.stat(
                target,
                dir_fd=kwargs["dst_dir_fd"],
                follow_symlinks=False,
            )
            installed_identity = (installed.st_dev, installed.st_ino)
            open_identities = set()
            for descriptor_name in os.listdir("/proc/self/fd"):
                try:
                    opened = os.fstat(int(descriptor_name))
                except (OSError, ValueError):
                    continue
                open_identities.add((opened.st_dev, opened.st_ino))
            self.assertIn(installed_identity, open_identities)
            os.unlink(target, dir_fd=kwargs["dst_dir_fd"])
            os.symlink(external, target, dir_fd=kwargs["dst_dir_fd"])

        with mock.patch.object(bridge.os, "replace", side_effect=swap_after_replace):
            with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
                self.store.save(ADDRESS)
        self.assertTrue(os.path.islink(self.path))
        self.assertEqual(stat.S_IMODE(os.stat(external).st_mode), 0o644)

    def test_post_replace_regular_inode_swap_is_detected_and_preserved(self):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700)
        replacement_name = ".other-writer"
        replacement_path = os.path.join(parent, replacement_name)
        with open(replacement_path, "wb") as replacement_file:
            replacement_file.write(
                json.dumps(
                    {"schemaVersion": 1, "selectedAddress": OTHER_ADDRESS},
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
        os.chmod(replacement_path, 0o600)
        original_replace = bridge.os.replace

        def swap_after_replace(source, target, **kwargs):
            original_replace(source, target, **kwargs)
            original_replace(
                replacement_name,
                target,
                src_dir_fd=kwargs["dst_dir_fd"],
                dst_dir_fd=kwargs["dst_dir_fd"],
            )

        with mock.patch.object(bridge.os, "replace", side_effect=swap_after_replace):
            with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
                self.store.save(ADDRESS)
        self.assertEqual(self.store.load(), (OTHER_ADDRESS, None))

    def test_post_replace_directory_fsync_failure_rolls_back_selection(self):
        real_fsync = bridge.os.fsync
        fsync_calls = 0

        def fail_directory_fsync(descriptor):
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 3:
                raise OSError("injected directory fsync failure")
            return real_fsync(descriptor)

        with mock.patch.object(bridge.os, "fsync", side_effect=fail_directory_fsync):
            with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
                self.store.save(ADDRESS)
        self.assertFalse(os.path.lexists(self.path))
        self.assertEqual(self.store.load(), (None, None))

    def test_rollback_restores_and_never_deletes_a_racing_writer_inode(self):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700)
        replacement_name = ".racing-writer"
        replacement_path = os.path.join(parent, replacement_name)
        with open(replacement_path, "wb") as replacement_file:
            replacement_file.write(
                json.dumps(
                    {"schemaVersion": 1, "selectedAddress": OTHER_ADDRESS},
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
        os.chmod(replacement_path, 0o600)

        real_fsync = bridge.os.fsync
        real_rename = bridge.os.rename
        raced = False

        def fail_parent_fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("injected directory fsync failure")
            return real_fsync(descriptor)

        def race_before_rollback(source, target, **kwargs):
            nonlocal raced
            if not raced and source == os.path.basename(self.path):
                raced = True
                os.replace(
                    replacement_name,
                    source,
                    src_dir_fd=kwargs["src_dir_fd"],
                    dst_dir_fd=kwargs["src_dir_fd"],
                )
            return real_rename(source, target, **kwargs)

        with mock.patch.object(bridge.os, "fsync", side_effect=fail_parent_fsync), mock.patch.object(
            bridge.os, "rename", side_effect=race_before_rollback
        ):
            with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
                self.store.save(ADDRESS)

        self.assertTrue(raced)
        self.assertEqual(self.store.load(), (OTHER_ADDRESS, None))
        self.assertEqual(os.listdir(parent), [os.path.basename(self.path)])

    def test_invalid_regular_file_can_be_replaced_atomically(self):
        self.write_raw(b"not json", mode=0o644)
        self.store.save(ADDRESS)
        self.assertEqual(self.store.load(), (ADDRESS, None))
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_save_rejects_symlink_and_nonregular_targets(self):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700)
        target = os.path.join(self.temporary.name, "elsewhere")
        with open(target, "wb") as target_file:
            target_file.write(b"safe")
        os.symlink(target, self.path)
        with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
            self.store.save(ADDRESS)
        with open(target, "rb") as target_file:
            self.assertEqual(target_file.read(), b"safe")
        os.unlink(self.path)
        os.mkdir(self.path)
        with self.assertRaisesRegex(bridge.BridgeError, "config_write_failed"):
            self.store.save(ADDRESS)

    def test_clear_deletes_only_an_owned_regular_local_record(self):
        self.store.save(ADDRESS)
        self.store.clear()
        self.assertFalse(os.path.lexists(self.path))
        self.store.clear()
        target = os.path.join(self.temporary.name, "elsewhere")
        with open(target, "wb") as target_file:
            target_file.write(b"safe")
        os.symlink(target, self.path)
        with self.assertRaisesRegex(bridge.BridgeError, "config_invalid"):
            self.store.clear()
        self.assertTrue(os.path.islink(self.path))


class JsonlValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, "omarchy", "io.github.filipechagas.freebuds.json")

    def run_process(self, data, controller=None, store=None):
        process = bridge.JsonlProcess(
            controller=controller or FakeController(),
            config_store=store or bridge.ConfigStore(self.path),
        )
        return_code, output, errors = serve_queued(process, data)
        return return_code, parse_lines(output), output.getvalue(), errors.getvalue(), process

    def test_one_hello_then_one_response_for_each_local_request(self):
        controller = FakeController()
        data = encoded_request(1, "clear_selection") + encoded_request(2, "shutdown")
        return_code, lines, _, _, _ = self.run_process(data, controller)
        self.assertEqual(return_code, 0)
        self.assertEqual([line["type"] for line in lines], ["hello", "result", "result"])
        self.assertEqual([line.get("id") for line in lines], [None, 1, 2])
        self.assertEqual(lines[0]["bridgeVersion"], "0.1.0")
        local_keys = {"v", "type", "id", "generation", "address", "selectedAddress"}
        self.assertEqual(set(lines[1]), local_keys)
        self.assertEqual(set(lines[2]), local_keys)
        self.assertIsNone(lines[1]["address"])
        self.assertIsNone(lines[2]["selectedAddress"])
        self.assertEqual(controller.refresh_calls, [])
        self.assertEqual(controller.anc_calls, [])

    def test_valid_config_address_is_loaded_only_into_hello(self):
        store = bridge.ConfigStore(self.path)
        store.save(ADDRESS)
        _, lines, _, _, _ = self.run_process(encoded_request(1, "shutdown"), store=store)
        self.assertEqual(lines[0]["selectedAddress"], ADDRESS)
        self.assertEqual(
            set(lines[0]),
            {"v", "type", "bridgeVersion", "selectedAddress"},
        )

    def test_invalid_config_is_reported_without_private_contact(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700)
        with open(self.path, "wb") as config_file:
            config_file.write(b"invalid private raw config")
        os.chmod(self.path, 0o600)
        controller = FakeController()
        data = encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=False)
        _, lines, _, errors, _ = self.run_process(data, controller)
        self.assertEqual([line["type"] for line in lines], ["error", "hello", "error"])
        self.assertEqual(lines[0], {"v": 1, "type": "error", "code": "config_invalid"})
        self.assertEqual(lines[1]["type"], "hello")
        self.assertEqual(lines[2]["code"], "config_invalid")
        self.assertEqual(controller.refresh_calls, [])
        self.assertNotIn(b"invalid private raw config", errors)

    def test_contended_startup_config_lock_reaches_final_hello_within_budget(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700)

        class AdvancingClock:
            def __init__(self):
                self.now = 50.0

            def __call__(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        clock = AdvancingClock()
        store = bridge.ConfigStore(self.path, clock=clock, sleep=clock.sleep)

        def contended_flock(_descriptor, _operation):
            raise BlockingIOError(errno.EAGAIN, "contended")

        with mock.patch.object(
            bridge, "CONFIG_LOCK_TIMEOUT_SECONDS", 0.03
        ), mock.patch.object(bridge.fcntl, "flock", side_effect=contended_flock):
            _, lines, _, _, _ = self.run_process(
                encoded_request(1, "shutdown"),
                store=store,
            )

        self.assertLess(bridge.CONFIG_LOCK_TIMEOUT_SECONDS, 2.0)
        self.assertLess(clock.now - 50.0, 0.04)
        self.assertEqual([line["type"] for line in lines], ["error", "hello", "result"])
        self.assertEqual(lines[0]["code"], "config_invalid")

    def test_overlong_invalid_utf8_malformed_duplicate_and_nonfinite_lines_fail_closed(self):
        invalid_lines = (
            b"x" * (bridge.MAX_JSONL_BYTES + 1) + b"\n",
            b"\xff\n",
            b"{\n",
            b'{"v":1,"v":1,"type":"request","id":1,"generation":1,"method":"shutdown"}\n',
            b'{"v":NaN,"type":"request","id":1,"generation":1,"method":"shutdown"}\n',
            b"[]\n",
            b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}\n",
        )
        for invalid in invalid_lines:
            with self.subTest(prefix=invalid[:20]):
                _, lines, _, _, _ = self.run_process(invalid)
                self.assertEqual(len(lines), 2)
                self.assertEqual(lines[1]["type"], "error")
                self.assertEqual(lines[1]["code"], "invalid_request")

    def test_overlong_line_is_drained_before_next_request(self):
        data = b"x" * (bridge.MAX_JSONL_BYTES + 1) + b"\n" + encoded_request(9, "shutdown")
        _, lines, _, _, _ = self.run_process(data)
        self.assertEqual([line["type"] for line in lines], ["hello", "error", "result"])
        self.assertEqual(lines[2]["id"], 9)

    def test_wrong_versions_types_unknown_fields_and_methods_fail_closed(self):
        base = request(1, "shutdown")
        invalid_values = []
        for key, value in (
            ("v", 2),
            ("v", True),
            ("type", "result"),
            ("id", True),
            ("id", -1),
            ("id", "1"),
            ("generation", 1.5),
            ("method", "unknown"),
        ):
            candidate = dict(base)
            candidate[key] = value
            invalid_values.append(candidate)
        candidate = dict(base)
        candidate["extra"] = 1
        invalid_values.append(candidate)
        invalid_values.extend(
            [
                request(1, "refresh", address=1, selectOnSuccess=True),
                request(1, "refresh", address=ADDRESS, selectOnSuccess=1),
                request(1, "set_anc", address=ADDRESS, mode="transparent"),
                request(1, "clear_selection", address=ADDRESS),
            ]
        )
        for value in invalid_values:
            with self.subTest(value=value):
                raw = json.dumps(value, separators=(",", ":")).encode() + b"\n"
                _, lines, _, _, _ = self.run_process(raw)
                self.assertEqual(lines[1]["type"], "error")
                self.assertEqual(lines[1]["code"], "invalid_request")

    def test_invalid_canonical_address_has_stable_code_and_no_contact(self):
        controller = FakeController()
        raw = encoded_request(1, "refresh", address="aa:bb:cc:dd:ee:ff", selectOnSuccess=True)
        _, lines, output, errors, _ = self.run_process(raw, controller)
        self.assertEqual(lines[1]["code"], "invalid_address")
        self.assertNotIn(b"aa:bb:cc:dd:ee:ff", output)
        self.assertNotIn(b"aa:bb:cc:dd:ee:ff", errors)
        self.assertEqual(controller.refresh_calls, [])

    def test_only_three_anc_mode_enums_validate(self):
        class Mode(str):
            pass

        for mode in ("off", "anc", "awareness"):
            candidate = request(1, "set_anc", address=ADDRESS, mode=mode)
            self.assertIs(bridge.validate_request(candidate), candidate)
        for mode in ("transparent", "on", "ANC", "", 1, None, ["anc"], {"anc": True}, Mode("anc")):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(bridge.BridgeError, "invalid_request"):
                    bridge.validate_request(request(1, "set_anc", address=ADDRESS, mode=mode))

    def test_error_code_vocabulary_is_exact_and_messages_are_redacted(self):
        expected = {
            "invalid_request",
            "busy",
            "config_invalid",
            "config_write_failed",
            "invalid_address",
            "transport_unsupported",
            "security_failed",
            "connect_failed",
            "transport_busy",
            "timeout",
            "socket_closed",
            "invalid_frame",
            "unexpected_response",
            "identity_mismatch",
            "identity_conflict",
            "battery_invalid",
            "anc_invalid",
            "anc_send_failed",
            "anc_readback_failed",
            "anc_readback_mismatch",
        }
        self.assertEqual(set(bridge.ERROR_MESSAGES), expected)
        with open(bridge.__file__, "r", encoding="utf-8") as source_file:
            self.assertNotIn("startup_failed", source_file.read())
        joined = " ".join(bridge.ERROR_MESSAGES.values())
        self.assertNotIn(ADDRESS, joined)
        self.assertNotIn("00016D", joined)


class JsonlSelectionAndRedactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, "omarchy", "io.github.filipechagas.freebuds.json")

    def run_process(self, data, controller, store=None):
        process = bridge.JsonlProcess(controller, store or bridge.ConfigStore(self.path))
        _, output, errors = serve_queued(process, data)
        return parse_lines(output), output.getvalue(), errors.getvalue()

    def test_selection_commits_only_after_verified_refresh_result(self):
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
            controller,
        )
        self.assertEqual(controller.refresh_calls, [ADDRESS])
        self.assertEqual(lines[1]["type"], "result")
        self.assertEqual(lines[1]["address"], ADDRESS)
        self.assertEqual(lines[1]["selectedAddress"], ADDRESS)
        self.assertTrue(lines[1]["verified"])
        self.assertEqual((lines[1]["left"], lines[1]["right"], lines[1]["case"]), (100, 100, 85))
        self.assertEqual(
            set(lines[1]),
            {
                "v", "type", "id", "generation", "address", "verified", "selectedAddress",
                "left", "right", "case", "anc", "batteryError", "ancError",
            },
        )
        self.assertEqual(bridge.ConfigStore(self.path).load(), (ADDRESS, None))

    def test_successful_anc_result_matches_model_wire_contract(self):
        store = bridge.ConfigStore(self.path)
        store.save(ADDRESS)
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "set_anc", address=ADDRESS, mode="awareness"),
            controller,
            store,
        )
        self.assertEqual(
            lines[1],
            {
                "v": 1,
                "type": "result",
                "id": 1,
                "generation": 4,
                "address": ADDRESS,
                "verified": True,
                "anc": "awareness",
            },
        )

    def test_identity_or_shape_failure_never_writes_config(self):
        for code in ("identity_mismatch", "identity_conflict", "battery_invalid", "anc_invalid"):
            if os.path.lexists(self.path):
                os.unlink(self.path)
            controller = FakeController(refresh_error=bridge.BridgeError(code))
            with self.subTest(code=code):
                lines, _, _ = self.run_process(
                    encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
                    controller,
                )
                self.assertEqual(lines[1]["type"], "error")
                self.assertEqual(lines[1]["code"], code)
                self.assertFalse(os.path.lexists(self.path))

    def test_invalid_regular_config_can_be_replaced_after_verified_selection(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700)
        with open(self.path, "wb") as config_file:
            config_file.write(b"invalid")
        os.chmod(self.path, 0o644)
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
            controller,
        )
        self.assertEqual(lines[0], {"v": 1, "type": "error", "code": "config_invalid"})
        self.assertEqual(lines[1]["type"], "hello")
        self.assertEqual(lines[2]["selectedAddress"], ADDRESS)
        self.assertEqual(bridge.ConfigStore(self.path).load(), (ADDRESS, None))

    def test_reverified_selection_replaces_a_stale_different_persisted_address(self):
        store = bridge.ConfigStore(self.path)
        store.save(OTHER_ADDRESS)
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
            controller,
            store,
        )
        self.assertEqual(controller.refresh_calls, [ADDRESS])
        self.assertEqual(lines[1]["selectedAddress"], ADDRESS)
        self.assertEqual(store.load(), (ADDRESS, None))

    def test_config_write_failure_suppresses_valid_private_product_state(self):
        class FailingStore(bridge.ConfigStore):
            def save(self, address):
                raise bridge.BridgeError("config_write_failed")

        controller = FakeController()
        lines, output, _ = self.run_process(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
            controller,
            FailingStore(self.path),
        )
        self.assertEqual([line["type"] for line in lines], ["hello", "error"])
        self.assertEqual(lines[1]["code"], "config_write_failed")
        self.assertNotIn(b'"battery"', output)
        self.assertNotIn(b'"readVerified"', output)

    def test_set_anc_requires_exact_persisted_address_before_contact(self):
        store = bridge.ConfigStore(self.path)
        store.save(ADDRESS)
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "set_anc", address=OTHER_ADDRESS, mode="anc"),
            controller,
            store,
        )
        self.assertEqual(lines[1]["code"], "invalid_address")
        self.assertEqual(controller.anc_calls, [])

    def test_set_anc_rechecks_the_current_persisted_address_before_contact(self):
        class ChangingStore:
            def __init__(self):
                self.loads = 0

            def load(self):
                self.loads += 1
                return ADDRESS, None

            def selection_lease(self):
                return bridge._SelectionLease(-1, OTHER_ADDRESS, None)

            def clear(self):
                raise AssertionError("clear called")

            def save(self, address):
                raise AssertionError("save called")

        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "set_anc", address=ADDRESS, mode="anc"),
            controller,
            ChangingStore(),
        )
        self.assertEqual(lines[1]["code"], "invalid_address")
        self.assertEqual(controller.anc_calls, [])

    def test_selection_lease_blocks_competing_writer_through_device_contact(self):
        for method, fields in (
            ("refresh", {"address": ADDRESS, "selectOnSuccess": False}),
            ("set_anc", {"address": ADDRESS, "mode": "anc"}),
        ):
            store = bridge.ConfigStore(self.path)
            store.save(ADDRESS)
            contact_started = threading.Event()
            release_contact = threading.Event()
            writer_contended = threading.Event()
            allow_writer_retry = threading.Event()

            class BlockingController(FakeController):
                def _block(self):
                    contact_started.set()
                    if not release_contact.wait(2.0):
                        raise AssertionError("device contact was not released")

                def refresh(self, address):
                    self.refresh_calls.append(address)
                    self._block()
                    return copy.deepcopy(self.refresh_result)

                def set_anc(self, address, mode):
                    self.anc_calls.append((address, mode))
                    self._block()
                    result = copy.deepcopy(self.anc_result)
                    result["anc"]["mode"] = mode
                    return result

            def wait_while_contended(_seconds):
                writer_contended.set()
                if not allow_writer_retry.wait(2.0):
                    raise AssertionError("writer retry was not released")

            controller = BlockingController()
            process = bridge.JsonlProcess(controller, store)
            transaction_outcome = []
            writer_outcome = []

            def execute_transaction():
                try:
                    transaction_outcome.append(process._execute_transaction(request(1, method, **fields)))
                except BaseException as error:
                    transaction_outcome.append(error)

            def replace_selection():
                try:
                    bridge.ConfigStore(self.path, sleep=wait_while_contended).save(OTHER_ADDRESS)
                except BaseException as error:
                    writer_outcome.append(error)

            transaction = threading.Thread(target=execute_transaction)
            writer = threading.Thread(target=replace_selection)
            with self.subTest(method=method):
                transaction.start()
                self.assertTrue(contact_started.wait(2.0))
                writer.start()
                self.assertTrue(writer_contended.wait(2.0))
                self.assertTrue(writer.is_alive())
                self.assertEqual(store.load(), (ADDRESS, None))

                release_contact.set()
                transaction.join(2.0)
                self.assertFalse(transaction.is_alive())
                allow_writer_retry.set()
                writer.join(2.0)

                self.assertFalse(writer.is_alive())
                self.assertEqual(writer_outcome, [])
                self.assertEqual(len(transaction_outcome), 1)
                self.assertIsInstance(transaction_outcome[0], dict)
                self.assertEqual(store.load(), (OTHER_ADDRESS, None))

    def test_set_anc_without_selection_never_contacts_transport(self):
        controller = FakeController()
        lines, _, _ = self.run_process(
            encoded_request(1, "set_anc", address=ADDRESS, mode="anc"),
            controller,
        )
        self.assertEqual(lines[1]["code"], "invalid_address")
        self.assertEqual(controller.anc_calls, [])

    def test_clear_selection_and_shutdown_never_call_transaction_controller(self):
        store = bridge.ConfigStore(self.path)
        store.save(ADDRESS)

        class NoContactController(FakeController):
            def refresh(self, address):
                raise AssertionError("refresh contacted")

            def set_anc(self, address, mode):
                raise AssertionError("ANC contacted")

        controller = NoContactController()
        lines, _, _ = self.run_process(
            encoded_request(1, "clear_selection") + encoded_request(2, "shutdown"),
            controller,
            store,
        )
        self.assertEqual([line["type"] for line in lines], ["hello", "result", "result"])
        self.assertFalse(os.path.exists(self.path))

    def test_injected_sensitive_exception_never_reaches_stdout_or_stderr(self):
        sensitive = "BTF0027-00016D SERIAL-PRIVATE 100/100/85"

        class ExplodingController(FakeController):
            def refresh(self, address):
                raise RuntimeError(f"{address} {sensitive}")

        lines, output, errors = self.run_process(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True),
            ExplodingController(),
        )
        self.assertEqual(lines[1]["code"], "socket_closed")
        self.assertEqual(lines[1]["address"], ADDRESS)
        self.assertEqual(
            set(lines[1]),
            {"v", "type", "id", "generation", "address", "code", "observedAnc"},
        )
        self.assertNotIn(sensitive.encode(), output)
        self.assertNotIn(ADDRESS.encode(), errors)
        self.assertNotIn(sensitive.encode(), errors)

    def test_mismatch_error_contains_only_validated_observation(self):
        error = bridge.BridgeError(
            "anc_readback_mismatch",
            {"observedMode": "awareness", "observedAt": 123.5, "raw": ADDRESS},
        )
        controller = FakeController(anc_error=error)
        store = bridge.ConfigStore(self.path)
        store.save(ADDRESS)
        lines, output, errors = self.run_process(
            encoded_request(1, "set_anc", address=ADDRESS, mode="anc"),
            controller,
            store,
        )
        self.assertEqual(lines[1]["observedAnc"], "awareness")
        self.assertNotIn(b'"raw"', output)
        self.assertNotIn(ADDRESS.encode(), errors)


class JsonlConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, "omarchy", "io.github.filipechagas.freebuds.json")

    def run_busy_case(self, second_id):
        started = threading.Event()
        release = threading.Event()

        class BlockingController(FakeController):
            def refresh(self, address):
                self.refresh_calls.append(address)
                started.set()
                release.wait(2.0)
                return copy.deepcopy(self.refresh_result)

        input_stream = QueueInput()
        output = RecordingStream()
        errors = RecordingStream()
        controller = BlockingController()
        process = bridge.JsonlProcess(controller, bridge.ConfigStore(self.path))
        server = threading.Thread(target=process.serve, args=(input_stream, output, errors))
        server.start()
        self.assertTrue(output.wait_for_lines(1))
        input_stream.feed(encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True))
        self.assertTrue(started.wait(2.0))
        input_stream.feed(encoded_request(second_id, "refresh", address=ADDRESS, selectOnSuccess=True))
        self.assertTrue(output.wait_for_lines(2))
        release.set()
        self.assertTrue(output.wait_for_lines(3))
        input_stream.close()
        server.join(2.0)
        self.assertFalse(server.is_alive())
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        return lines, controller

    def test_second_active_request_is_busy_and_never_queued(self):
        lines, controller = self.run_busy_case(2)
        self.assertEqual(lines[1]["id"], 2)
        self.assertEqual(lines[1]["code"], "busy")
        self.assertEqual(lines[2]["id"], 1)
        self.assertEqual(lines[2]["type"], "result")
        self.assertEqual(controller.refresh_calls, [ADDRESS])

    def test_duplicate_active_id_is_invalid_and_never_queued(self):
        lines, controller = self.run_busy_case(1)
        self.assertEqual(lines[1]["id"], 1)
        self.assertEqual(lines[1]["code"], "invalid_request")
        self.assertEqual(lines[2]["type"], "result")
        self.assertEqual(controller.refresh_calls, [ADDRESS])

    def test_completed_or_out_of_order_id_is_rejected_without_execution(self):
        input_stream = (
            encoded_request(2, "clear_selection")
            + encoded_request(2, "clear_selection")
            + encoded_request(1, "clear_selection")
            + encoded_request(3, "shutdown")
        )
        output = io.BytesIO()
        errors = io.BytesIO()
        controller = FakeController()
        process = bridge.JsonlProcess(controller, bridge.ConfigStore(self.path))
        process.serve(io.BytesIO(input_stream), output, errors)
        lines = parse_lines(output)
        self.assertEqual([line["type"] for line in lines], ["hello", "result", "error", "error", "result"])
        self.assertEqual([lines[2]["code"], lines[3]["code"]], ["invalid_request", "invalid_request"])
        self.assertEqual(controller.refresh_calls, [])
        self.assertEqual(controller.anc_calls, [])

    def test_invalid_high_id_does_not_advance_the_accepted_id_high_water_mark(self):
        input_stream = (
            encoded_request(99, "unknown")
            + encoded_request(1, "clear_selection")
            + encoded_request(2, "shutdown")
        )
        output = io.BytesIO()
        errors = io.BytesIO()
        process = bridge.JsonlProcess(FakeController(), bridge.ConfigStore(self.path))
        process.serve(io.BytesIO(input_stream), output, errors)
        lines = parse_lines(output)
        self.assertEqual([line["type"] for line in lines], ["hello", "error", "result", "result"])
        self.assertEqual([lines[1]["id"], lines[2]["id"], lines[3]["id"]], [99, 1, 2])
        self.assertEqual(lines[1]["code"], "invalid_request")

    def test_terminal_state_is_cleared_before_response_drives_next_request(self):
        clear_started = threading.Event()

        class SignalingStore(bridge.ConfigStore):
            def clear(self):
                clear_started.set()
                return super().clear()

        store = SignalingStore(self.path)
        store.save(ADDRESS)
        input_stream = QueueInput()

        class ResponseDrivenOutput(RecordingStream):
            def __init__(self):
                super().__init__()
                self.clear_was_ready = False

            def write(self, value):
                written = super().write(value)
                message = json.loads(value)
                if message.get("type") == "result" and message.get("id") == 1:
                    input_stream.feed(encoded_request(2, "clear_selection"))
                    self.clear_was_ready = clear_started.wait(2.0)
                return written

        output = ResponseDrivenOutput()
        errors = RecordingStream()
        controller = FakeController()
        process = bridge.JsonlProcess(controller, store)
        server = threading.Thread(target=process.serve, args=(input_stream, output, errors))
        server.start()
        self.assertTrue(output.wait_for_type("hello"))
        input_stream.feed(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=False)
        )
        self.assertTrue(output.wait_for_lines(3))
        input_stream.close()
        server.join(2.0)

        self.assertFalse(server.is_alive())
        self.assertTrue(output.clear_was_ready)
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(
            [(line["type"], line.get("id"), line.get("code")) for line in lines],
            [("hello", None, None), ("result", 1, None), ("result", 2, None)],
        )

    def test_shutdown_cannot_overtake_terminal_publication_boundary(self):
        boundary_entered = threading.Event()
        release_boundary = threading.Event()
        shutdown_rejected = threading.Event()

        class PausingProcess(bridge.JsonlProcess):
            def _release_active_for_terminal(self, worker):
                boundary_entered.set()
                if not release_boundary.wait(2.0):
                    raise AssertionError("terminal boundary was not released")
                return super()._release_active_for_terminal(worker)

            def _emit_error(self, request_id, generation, error, address=None):
                if request_id == 2 and error.code == "busy":
                    shutdown_rejected.set()
                return super()._emit_error(request_id, generation, error, address)

        input_stream = QueueInput()
        output = RecordingStream()
        errors = RecordingStream()
        controller = FakeController()
        process = PausingProcess(controller, bridge.ConfigStore(self.path))
        server = threading.Thread(target=process.serve, args=(input_stream, output, errors))
        server.start()
        self.assertTrue(output.wait_for_type("hello"))
        input_stream.feed(
            encoded_request(1, "refresh", address=ADDRESS, selectOnSuccess=True)
        )
        self.assertTrue(boundary_entered.wait(2.0))

        input_stream.feed(encoded_request(2, "shutdown"))
        self.assertTrue(shutdown_rejected.wait(2.0))
        release_boundary.set()
        self.assertTrue(output.wait_for_lines(3))
        input_stream.close()
        server.join(2.0)

        self.assertFalse(server.is_alive())
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(
            [(line["type"], line.get("id"), line.get("code")) for line in lines],
            [("hello", None, None), ("result", 1, None), ("error", 2, "busy")],
        )

    def test_uncooperative_daemon_worker_is_joined_boundedly_and_silenced_after_stop(self):
        started = threading.Event()
        release = threading.Event()

        class UncooperativeController(FakeController):
            def refresh(self, address):
                self.refresh_calls.append(address)
                started.set()
                release.wait(2.0)
                raise bridge.BridgeError("socket_closed")

        controller = UncooperativeController()
        process = bridge.JsonlProcess(controller, bridge.ConfigStore(self.path))
        join_calls = []

        class RequestThenFailure:
            def __init__(self):
                self.calls = 0
                self.worker = None
                self.original_join = None

            def readline(self, _limit):
                self.calls += 1
                if self.calls == 1:
                    return encoded_request(
                        1,
                        "refresh",
                        address=ADDRESS,
                        selectOnSuccess=True,
                    )
                self.assert_started()
                with process._state_lock:
                    self.worker = process._active_thread
                self.original_join = self.worker.join

                def recording_join(timeout=None):
                    join_calls.append(timeout)
                    return self.original_join(timeout)

                self.worker.join = recording_join
                raise RuntimeError("injected input failure")

            @staticmethod
            def assert_started():
                if not started.wait(2.0):
                    raise AssertionError("worker did not start")

        input_stream = RequestThenFailure()
        output = io.BytesIO()
        errors = io.BytesIO()
        with mock.patch.object(bridge, "WORKER_JOIN_TIMEOUT_SECONDS", 0.05):
            with self.assertRaisesRegex(RuntimeError, "injected input failure"):
                process.serve(input_stream, output, errors)

        worker = input_stream.worker
        self.assertTrue(worker.daemon)
        self.assertTrue(worker.is_alive())
        self.assertEqual(controller.cancel_calls, 1)
        self.assertEqual(len(join_calls), 1)
        self.assertGreaterEqual(join_calls[0], 0.0)
        self.assertLessEqual(join_calls[0], 0.05)
        stopped_output = output.getvalue()
        self.assertEqual([line["type"] for line in parse_lines(output)], ["hello"])

        release.set()
        input_stream.original_join(1.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(output.getvalue(), stopped_output)
        self.assertEqual(errors.getvalue(), b"")


class ProcessAndStaticAuditTests(unittest.TestCase):
    def test_subprocess_hello_shutdown_smoke_exits_without_config_or_stderr(self):
        with tempfile.TemporaryDirectory() as config_home:
            environment = dict(os.environ)
            environment["XDG_CONFIG_HOME"] = config_home
            started = time.monotonic()
            child = subprocess.Popen(
                [sys.executable, bridge.__file__, "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
            )
            stdout, stderr = child.communicate(encoded_request(7, "shutdown", generation=9), timeout=5.0)
            elapsed = time.monotonic() - started
            self.assertEqual(child.returncode, 0)
            self.assertLess(elapsed, 2.0)
            lines = [json.loads(line) for line in stdout.splitlines()]
            self.assertEqual([line["type"] for line in lines], ["hello", "result"])
            self.assertEqual(lines[0]["selectedAddress"], None)
            self.assertEqual((lines[1]["id"], lines[1]["generation"]), (7, 9))
            self.assertEqual(stderr, b"")
            self.assertEqual(os.listdir(config_home), [])

    def test_stdout_is_entirely_compact_protocol_jsonl(self):
        output = io.BytesIO()
        errors = io.BytesIO()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "omarchy", "io.github.filipechagas.freebuds.json")
            process = bridge.JsonlProcess(FakeController(), bridge.ConfigStore(path))
            process.serve(io.BytesIO(b"not-json\n" + encoded_request(2, "shutdown")), output, errors)
        for line in output.getvalue().splitlines():
            parsed = json.loads(line)
            self.assertIsInstance(parsed, dict)
            self.assertEqual(json.dumps(parsed, ensure_ascii=True, separators=(",", ":")).encode(), line)
        self.assertIn(b"invalid_request", errors.getvalue())
        self.assertNotIn(b"bridge:", output.getvalue())

    def test_ast_import_allowlist_is_standard_library_only(self):
        with open(bridge.__file__, "r", encoding="utf-8") as source_file:
            tree = ast.parse(source_file.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(
            imported,
            {
                "binascii",
                "errno",
                "fcntl",
                "json",
                "math",
                "os",
                "re",
                "select",
                "socket",
                "stat",
                "struct",
                "sys",
                "threading",
                "time",
            },
        )

    def test_ast_proves_no_import_time_socket_and_one_fixed_construction_site(self):
        with open(bridge.__file__, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        tree = ast.parse(source)
        direct_socket_calls = []
        factory_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "socket"
                and node.func.attr == "socket"
            ):
                direct_socket_calls.append(node)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "_socket_factory":
                factory_calls.append(node)
        self.assertEqual(direct_socket_calls, [])
        self.assertEqual(len(factory_calls), 1)
        call = factory_calls[0]
        self.assertEqual(len(call.args), 3)
        self.assertIsInstance(call.args[0], ast.Name)
        self.assertEqual(call.args[0].id, "family")
        self.assertIsInstance(call.args[1], ast.Attribute)
        self.assertEqual(call.args[1].attr, "SOCK_STREAM")
        self.assertIsInstance(call.args[2], ast.Name)
        self.assertEqual(call.args[2].id, "protocol")
        production_classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name in {"RfcommTransport", "TransactionController"}
        }
        forbidden_arguments = {"frame", "packet", "channel", "security_level", "retry_count"}
        for class_node in production_classes.values():
            for node in class_node.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arguments = {argument.arg for argument in node.args.args}
                    self.assertFalse(arguments & forbidden_arguments, (class_node.name, node.name, arguments))
        self.assertFalse(hasattr(bridge.RfcommTransport, "send"))
        for forbidden in (
            "AF_INET",
            "AF_INET6",
            "SOCK_DGRAM",
            "urllib",
            "http.client",
            "requests",
            "websocket",
            "dbus",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
