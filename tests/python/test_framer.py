import random
import unittest

from bridge import freebuds_bridge as bridge


CAPTURED_BATTERY = bytes.fromhex(
    "5A001B0001080101640203646455030300000004020A140502000106010A4D9B"
)
CAPTURED_ANC = {
    "off": bytes.fromhex("5A000A002B2A01020000020105B843"),
    "anc": bytes.fromhex("5A000A002B2A010203010201052025"),
    "awareness": bytes.fromhex("5A000A002B2A0102020202010511A8"),
}
SYNTHETIC_00016D_PREFIX = b"BTF0027"


def independent_crc(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(service, command, tlvs=(), version=0):
    body = bytes((version, service, command))
    for tag, value in tlvs:
        body += bytes((tag, len(value))) + value
    prefix = b"\x5A" + len(body).to_bytes(2, "big") + body
    return prefix + independent_crc(prefix).to_bytes(2, "big")


def raw_body_frame(body):
    prefix = b"\x5A" + len(body).to_bytes(2, "big") + body
    return prefix + independent_crc(prefix).to_bytes(2, "big")


def synthetic_identity(overrides=None, omit=()):
    values = {
        0x02: b"\x01\x6D",
        0x0A: SYNTHETIC_00016D_PREFIX + b"-00016D",
        0x0F: SYNTHETIC_00016D_PREFIX,
        0x19: b"\x02",
    }
    values.update(overrides or {})
    return frame(0x01, 0x07, [(tag, value) for tag, value in values.items() if tag not in omit])


class RetainedFrameTests(unittest.TestCase):
    def test_captured_startup_frame_is_byte_exact(self):
        self.assertEqual(bridge.STARTUP_FRAME.hex().upper(), "5A00030001063EBD")
        self.assertEqual(
            bridge.parse_frame(bridge.STARTUP_FRAME),
            {
                "service": 0x01,
                "command": 0x06,
                "tlvs": (),
            },
        )

    def test_immutable_frames_are_byte_exact(self):
        expected = (
            "5A00210001070100020003000400050006000700080009000A000B000C000F0018001900DFF3",
            "5A0009000108010002000300FBB9",
            "5A0005002B2A0100427E",
            "5A0007002B0401020000D22D",
            "5A0007002B04010201FFFFEC",
            "5A0007002B04010202FFAABF",
        )
        self.assertEqual(tuple(item.hex().upper() for item in bridge.RETAINED_FRAMES), expected)

    def test_retained_lengths_and_crcs_are_independently_valid(self):
        for retained in bridge.RETAINED_FRAMES:
            with self.subTest(frame=retained.hex()):
                self.assertEqual(len(retained), int.from_bytes(retained[1:3], "big") + 5)
                self.assertEqual(independent_crc(retained[:-2]), int.from_bytes(retained[-2:], "big"))

    def test_startup_self_check_accepts_corpus(self):
        self.assertIsNone(bridge.validate_retained_frames())

    def test_every_split_point_for_every_retained_frame(self):
        for retained in bridge.RETAINED_FRAMES:
            expected = bridge.parse_frame(retained)
            for split_at in range(len(retained) + 1):
                with self.subTest(frame=retained.hex(), split_at=split_at):
                    decoder = bridge.FrameStreamDecoder()
                    parsed = decoder.feed(retained[:split_at])
                    parsed.extend(decoder.feed(retained[split_at:]))
                    decoder.finish()
                    self.assertEqual(parsed, [expected])


class StreamDecoderTests(unittest.TestCase):
    def test_two_and_three_frames_in_one_read(self):
        decoder = bridge.FrameStreamDecoder()
        two = decoder.feed(bridge.BATTERY_QUERY + bridge.ANC_QUERY)
        three = decoder.feed(bridge.DEVICE_INFO_QUERY + bridge.BATTERY_QUERY + bridge.ANC_QUERY)
        self.assertEqual(len(two), 2)
        self.assertEqual(len(three), 3)
        self.assertEqual([(item["service"], item["command"]) for item in two], [(1, 8), (0x2B, 0x2A)])

    def test_garbage_before_magic_and_between_frames_is_discarded(self):
        decoder = bridge.FrameStreamDecoder()
        parsed = decoder.feed(b"garbage" + bridge.BATTERY_QUERY + b"\x00\x01junk" + bridge.ANC_QUERY)
        self.assertEqual([(item["service"], item["command"]) for item in parsed], [(1, 8), (0x2B, 0x2A)])

    def test_minimum_frame_is_valid(self):
        minimum = frame(1, 7)
        self.assertEqual(len(minimum), 8)
        self.assertEqual(bridge.parse_frame(minimum)["tlvs"], ())

    def test_exact_maximum_frame_is_valid(self):
        tlvs = [(0xFE, bytes(255)) for _ in range(15)]
        tlvs.append((0xFD, bytes(231)))
        maximum = frame(0x7E, 0x7F, tlvs)
        self.assertEqual(len(maximum), bridge.MAX_FRAME_BYTES)
        self.assertEqual(len(bridge.parse_frame(maximum)["tlvs"]), 16)

    def test_over_limit_declared_frame_fails_before_waiting(self):
        decoder = bridge.FrameStreamDecoder()
        declared = bridge.MAX_FRAME_BYTES - 4
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            decoder.feed(b"\x5A" + declared.to_bytes(2, "big"))

    def test_declared_length_below_minimum_is_rejected(self):
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            bridge.FrameStreamDecoder().feed(b"\x5A\x00\x02")

    def test_wrong_version_is_rejected(self):
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            bridge.parse_frame(frame(1, 8, version=1))

    def test_bad_crc_is_rejected(self):
        damaged = bytearray(bridge.BATTERY_QUERY)
        damaged[-1] ^= 1
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            bridge.parse_frame(damaged)

    def test_truncated_frame_is_rejected_at_eof(self):
        decoder = bridge.FrameStreamDecoder()
        self.assertEqual(decoder.feed(bridge.BATTERY_QUERY[:-1]), [])
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            decoder.finish()

    def test_truncated_tlv_is_rejected_even_with_valid_outer_crc(self):
        malformed = raw_body_frame(b"\x00\x01\x08\x02\x02\x64")
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            bridge.parse_frame(malformed)

    def test_unknown_well_formed_tlv_is_retained_without_semantics(self):
        identity = synthetic_identity()
        parsed = bridge.parse_frame(identity)
        unknown_identity = frame(1, 7, list(parsed["tlvs"]) + [(0xEE, b"opaque")])
        parsed_unknown = bridge.parse_frame(unknown_identity)
        self.assertIn((0xEE, b"opaque"), parsed_unknown["tlvs"])
        self.assertEqual(bridge.decode_device_identity(parsed_unknown), {"verified": True})

    def test_duplicate_unknown_tlv_remains_uninterpreted(self):
        parsed = bridge.parse_frame(frame(0x70, 0x71, [(0xEE, b"a"), (0xEE, b"b")]))
        self.assertEqual(parsed["tlvs"], ((0xEE, b"a"), (0xEE, b"b")))

    def test_duplicate_known_tlv_is_rejected_by_semantic_decoder(self):
        duplicate = frame(1, 8, [(2, b"\x64\x64\x55"), (2, b"\x64\x64\x55"), (5, b"\x00\x01")])
        with self.assertRaisesRegex(bridge.BridgeError, "battery_invalid"):
            bridge.decode_battery(duplicate)

    def test_unexpected_pair_is_rejected_for_active_request(self):
        with self.assertRaisesRegex(bridge.BridgeError, "unexpected_response"):
            bridge.decode_battery(CAPTURED_ANC["off"])

    def test_crc_is_checked_before_response_pair(self):
        damaged = bytearray(CAPTURED_ANC["off"])
        damaged[-1] ^= 1
        with self.assertRaisesRegex(bridge.BridgeError, "invalid_frame"):
            bridge.decode_battery(damaged)


class SemanticDecoderTests(unittest.TestCase):
    def test_three_captured_extended_anc_modes(self):
        for expected, captured in CAPTURED_ANC.items():
            with self.subTest(mode=expected):
                self.assertEqual(bridge.decode_anc(captured), {"mode": expected})

    def test_short_other_model_anc_shape_is_rejected(self):
        shorter = bytes.fromhex("5A0007002B2A010203015043")
        with self.assertRaisesRegex(bridge.BridgeError, "anc_invalid"):
            bridge.decode_anc(shorter)

    def test_anc_marker_must_be_exact(self):
        for marker in (b"", b"\x04", b"\x05\x00"):
            with self.subTest(marker=marker):
                candidate = frame(0x2B, 0x2A, [(1, b"\x03\x01"), (2, marker)])
                with self.assertRaisesRegex(bridge.BridgeError, "anc_invalid"):
                    bridge.decode_anc(candidate)

    def test_anc_mode_uses_second_byte_only_but_rejects_unknown_mode(self):
        self.assertEqual(
            bridge.decode_anc(frame(0x2B, 0x2A, [(1, b"\xFF\x01"), (2, b"\x05")])),
            {"mode": "anc"},
        )
        with self.assertRaisesRegex(bridge.BridgeError, "anc_invalid"):
            bridge.decode_anc(frame(0x2B, 0x2A, [(1, b"\x00\x03"), (2, b"\x05")]))

    def test_captured_component_battery_decodes_components_and_case_presence(self):
        self.assertEqual(
            bridge.decode_battery(CAPTURED_BATTERY),
            {"left": 100, "right": 100, "case": 85, "leftInCase": False, "rightInCase": True},
        )

    def test_zero_is_preserved_as_a_real_percentage(self):
        candidate = frame(1, 8, [(2, b"\x00\x32\x00"), (5, b"\x00\x01")])
        self.assertEqual(bridge.decode_battery(candidate), {"left": 0, "right": 50, "case": 0, "leftInCase": False, "rightInCase": True})

    def test_percentage_above_100_is_rejected_not_clamped(self):
        candidate = frame(1, 8, [(2, b"\x65\x64\x55"), (5, b"\x00\x01")])
        with self.assertRaisesRegex(bridge.BridgeError, "battery_invalid"):
            bridge.decode_battery(candidate)

    def test_battery_requires_exact_component_and_presence_shapes(self):
        invalid_tlvs = (
            [(5, b"\x00\x01")],
            [(2, b"\x64\x64"), (5, b"\x00\x01")],
            [(2, b"\x64\x64\x55")],
            [(2, b"\x64\x64\x55"), (5, b"\x00")],
            [(2, b"\x64\x64\x55"), (5, b"\x00\x02")],
        )
        for tlvs in invalid_tlvs:
            with self.subTest(tlvs=tlvs):
                with self.assertRaisesRegex(bridge.BridgeError, "battery_invalid"):
                    bridge.decode_battery(frame(1, 8, tlvs))

    def test_clearly_synthetic_00016d_identity_is_accepted_for_parser_tests(self):
        self.assertEqual(bridge.decode_device_identity(synthetic_identity()), {"verified": True})

    def test_identity_requires_every_known_field(self):
        for missing in (0x02, 0x0A, 0x0F, 0x19):
            with self.subTest(missing=missing):
                with self.assertRaises(bridge.BridgeError):
                    bridge.decode_device_identity(synthetic_identity(omit={missing}))

    def test_identity_rejects_every_duplicate_known_field(self):
        parsed = bridge.parse_frame(synthetic_identity())
        for duplicate_tag in (0x02, 0x0A, 0x0F, 0x19):
            tlvs = list(parsed["tlvs"])
            value = next(value for tag, value in tlvs if tag == duplicate_tag)
            tlvs.append((duplicate_tag, value))
            with self.subTest(tag=duplicate_tag):
                with self.assertRaisesRegex(bridge.BridgeError, "identity_conflict"):
                    bridge.decode_device_identity(frame(1, 7, tlvs))

    def test_identity_rejects_non_ascii_and_oversized_values(self):
        candidates = (
            synthetic_identity({0x0A: b"BTF-00016\xFF"}),
            synthetic_identity({0x0F: b"BTF\xFF"}),
            synthetic_identity({0x0A: b"A" * 58 + b"-00016D"}),
            synthetic_identity({0x0F: b"A" * 65}),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate.hex()):
                with self.assertRaisesRegex(bridge.BridgeError, "identity_mismatch"):
                    bridge.decode_device_identity(candidate)

    def test_identity_rejects_conflicting_model_code_and_prefix(self):
        for overrides in ({0x02: b"\x00\x01"}, {0x0F: b"OTHER"}):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(bridge.BridgeError, "identity_conflict"):
                    bridge.decode_device_identity(synthetic_identity(overrides))

    def test_identity_rejects_non_target_and_malformed_model_values(self):
        candidates = (
            synthetic_identity({0x02: b"\x01\x63", 0x0A: SYNTHETIC_00016D_PREFIX + b"-000163"}),
            synthetic_identity({0x0A: b"BTF0027-00016d"}),
            synthetic_identity({0x0A: b"00016D"}),
            synthetic_identity({0x19: b""}),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate.hex()):
                with self.assertRaisesRegex(bridge.BridgeError, "identity_mismatch"):
                    bridge.decode_device_identity(candidate)


class DeterministicMutationTests(unittest.TestCase):
    def test_fixed_seed_mutations_are_bounded_and_contained(self):
        random_source = random.Random(0x00016D)
        corpus = [
            bridge.STARTUP_FRAME,
            bridge.ANC_WRITE_ACK,
            *bridge.RETAINED_FRAMES,
            CAPTURED_BATTERY,
            *CAPTURED_ANC.values(),
            synthetic_identity(),
        ]
        for iteration in range(1000):
            original = bytearray(random_source.choice(corpus))
            mutation_count = random_source.randint(1, 4)
            for _ in range(mutation_count):
                if original and random_source.randrange(4) == 0:
                    del original[random_source.randrange(len(original))]
                elif original and random_source.randrange(4) == 1:
                    original.insert(random_source.randrange(len(original) + 1), random_source.randrange(256))
                elif original:
                    index = random_source.randrange(len(original))
                    original[index] ^= 1 << random_source.randrange(8)
                else:
                    original.append(random_source.randrange(256))
            decoder = bridge.FrameStreamDecoder()
            try:
                decoder.feed(original)
                decoder.finish()
            except bridge.BridgeError as error:
                self.assertIn(error.code, bridge.ERROR_MESSAGES)
            except Exception as error:  # pragma: no cover - this assertion reports the unexpected type.
                self.fail(f"mutation {iteration} escaped containment: {type(error).__name__}")
            self.assertLessEqual(len(decoder._buffer), bridge.MAX_FRAME_BYTES)


if __name__ == "__main__":
    unittest.main()
