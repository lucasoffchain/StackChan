import asyncio
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

import monitor


class ProtocolTests(unittest.TestCase):
    def test_fragment_matches_firmware_and_reassembles_utf8(self):
        value = {"message": "构建运行中" * 12}
        frames = monitor.fragment_json(value)
        chunks = []
        for index, frame in enumerate(frames):
            self.assertLessEqual(len(frame), 20)
            magic, sequence, count, length = struct.unpack(">4sHHH", frame[:10])
            self.assertEqual(magic, b"\xaa\x55\xc3\x01")
            self.assertEqual(sequence, index)
            self.assertEqual(count, len(frames))
            chunks.append(frame[10:])
        raw = b"".join(chunks)
        self.assertEqual(len(raw), length)
        self.assertEqual(json.loads(raw), value)

    def test_small_message_is_not_framed(self):
        self.assertEqual(monitor.fragment_json({}), [b"{}"])

    def test_size_limits(self):
        with self.assertRaises(ValueError):
            monitor.fragment_json({"x": "a" * 2048})
        with self.assertRaises(ValueError):
            monitor.fragment_json({}, payload_size=10)

    def test_all_styles_use_supported_fields(self):
        for state in monitor.STYLES:
            payloads = dict(monitor.status_payloads(state))
            self.assertEqual(set(payloads), {monitor.AVATAR_UUID, monitor.RGB_UUID})
            self.assertEqual(set(payloads[monitor.AVATAR_UUID]), {"leftEye", "rightEye", "mouth", "modifyLock"})
            self.assertRegex(payloads[monitor.RGB_UUID]["leftRgbColor"], r"^#[0-9A-Fa-f]{6}$")

    def test_full_poses_reset_fields_and_use_firmware_ranges(self):
        for state in monitor.STYLES:
            avatar = monitor.status_payloads(state)[0][1]
            for key in ("leftEye", "rightEye", "mouth"):
                feature = avatar[key]
                self.assertTrue(0 <= feature["weight"] <= 100)
                self.assertTrue(0 <= feature["rotation"] < 3600)
                self.assertTrue(-100 <= feature["x"] <= 100)
                self.assertTrue(-100 <= feature["y"] <= 100)
            self.assertGreater(len(monitor.fragment_json(avatar)), 1)

    def test_text_is_opt_in_and_fits_firmware_limit(self):
        for state in monitor.STYLES:
            self.assertNotIn("speech", monitor.status_payloads(state)[0][1])
            for language in monitor.STATUS_TEXT:
                text = monitor.status_payloads(state, language)[0][1]["speech"]
                self.assertLessEqual(len(text.encode("utf-8")), 192)
                self.assertEqual(monitor.status_payloads(state, language)[0][1]["title"], "GROK")

    def test_dynamic_states_animate_features_without_changing_text_or_color(self):
        for state in ("thinking", "working", "done", "error", "waiting"):
            first = dict(monitor.status_payloads(state, "en", phase=0))
            second = dict(monitor.status_payloads(state, "en", phase=1))
            self.assertNotEqual(first[monitor.AVATAR_UUID], second[monitor.AVATAR_UUID])
            self.assertEqual(first[monitor.RGB_UUID], second[monitor.RGB_UUID])
            self.assertEqual(first[monitor.AVATAR_UUID]["speech"], second[monitor.AVATAR_UUID]["speech"])

    def test_negotiated_mtu_avoids_slow_minimum_size_fragmentation(self):
        writes = []

        class Client:
            mtu_size = 512

            async def write_gatt_char(self, characteristic, packet, *, response):
                self.assert_response = response
                writes.append((characteristic, packet))

        asyncio.run(monitor.send_state(Client(), "working", "en"))
        self.assertEqual(len(writes), 2)
        self.assertTrue(all(len(packet) <= 509 for _, packet in writes))
        self.assertEqual(json.loads(writes[0][1])["speech"], "Grok: Working...")

    def test_writes_are_acknowledged_and_in_order(self):
        writes = []

        class Client:
            async def write_gatt_char(self, characteristic, packet, *, response):
                writes.append((characteristic, packet, response))

        asyncio.run(monitor.send_state(Client(), "working"))
        expected = [
            (characteristic, packet, True)
            for characteristic, value in monitor.status_payloads("working")
            for packet in monitor.fragment_json(value)
        ]
        self.assertEqual(writes, expected)

    def test_grok_view_includes_state_and_text_in_one_message(self):
        for state in monitor.STYLES:
            avatar = monitor.status_payloads(state, skin="grok")[0][1]
            self.assertEqual(avatar["monitor"]["state"], state)
            self.assertTrue(avatar["monitor"]["text"])
            self.assertLess(len(monitor.fragment_json(avatar, 509)), 3)
        self.assertEqual(monitor.status_payloads("idle", skin="default")[0][1]["monitor"], {"skin": "default"})
        self.assertEqual(monitor.status_payloads("working", skin="grok")[0][1]["monitor"]["text"], "正在执行")
        self.assertEqual(monitor.status_payloads("working", "en", skin="grok")[0][1]["monitor"]["text"], "Working...")


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "status.json"

    def test_atomic_publish_and_heartbeat_expiry(self):
        monitor.write_state(self.path, "working")
        os.utime(self.path, (100, 100))
        self.assertEqual(monitor.read_state(self.path, 30, now=110), ("working", ""))
        self.assertEqual(monitor.read_state(self.path, 30, now=131)[0], "offline")
        monitor.write_state(self.path, "done")
        self.assertEqual(monitor.read_state(self.path, 30)[0], "done")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_missing_and_invalid_status_never_report_success(self):
        self.assertEqual(monitor.read_state(self.path, 30)[0], "unknown")
        for raw in ('{', '[]', '{"state":"bogus"}', '{"state":[]}', '"done"', 'x' * 4097):
            self.path.write_text(raw, encoding="utf-8")
            self.assertEqual(monitor.read_state(self.path, 30)[0], "unknown")


if __name__ == "__main__":
    unittest.main()
