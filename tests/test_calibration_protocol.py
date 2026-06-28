"""Unit tests for the calibration diagnostics/control protocol."""

from __future__ import annotations

import json
import unittest

from calibration_protocol import (
    SCHEMA_VERSION,
    ProtocolError,
    decode_message,
    encode_message,
    make_ack,
    make_error,
    make_request,
    make_telemetry,
    parse_message_dict,
)


class TestMakeRequest(unittest.TestCase):
    def test_contains_required_fields(self):
        msg = make_request("ping", session_id="s1", payload={"k": "v"})
        self.assertEqual(msg["schema_version"], SCHEMA_VERSION)
        self.assertEqual(msg["message_type"], "request")
        self.assertEqual(msg["action"], "ping")
        self.assertEqual(msg["session_id"], "s1")
        self.assertEqual(msg["payload"], {"k": "v"})
        self.assertIn("request_id", msg)
        self.assertIn("timestamp_ms", msg)

    def test_request_ids_are_unique(self):
        ids = {make_request("ping", session_id=None, payload={})["request_id"] for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_session_id_none_allowed(self):
        msg = make_request("ping", session_id=None, payload={})
        self.assertIsNone(msg["session_id"])


class TestMakeAck(unittest.TestCase):
    def test_contains_required_fields(self):
        msg = make_ack("req-1", session_id="s1", payload={"ok": True})
        self.assertEqual(msg["schema_version"], SCHEMA_VERSION)
        self.assertEqual(msg["message_type"], "ack")
        self.assertEqual(msg["request_id"], "req-1")
        self.assertEqual(msg["session_id"], "s1")
        self.assertEqual(msg["payload"], {"ok": True})


class TestMakeError(unittest.TestCase):
    def test_contains_required_fields(self):
        msg = make_error("req-2", session_id="s1", code="BAD", message="bad thing")
        self.assertEqual(msg["schema_version"], SCHEMA_VERSION)
        self.assertEqual(msg["message_type"], "error")
        self.assertEqual(msg["request_id"], "req-2")
        self.assertEqual(msg["error"]["code"], "BAD")
        self.assertEqual(msg["error"]["message"], "bad thing")

    def test_request_id_can_be_none(self):
        msg = make_error(None, session_id=None, code="X", message="y")
        self.assertIsNone(msg["request_id"])


class TestMakeTelemetry(unittest.TestCase):
    def test_contains_required_fields(self):
        msg = make_telemetry("live_metrics", session_id="s1", payload={"rms": 0.1})
        self.assertEqual(msg["schema_version"], SCHEMA_VERSION)
        self.assertEqual(msg["message_type"], "telemetry")
        self.assertEqual(msg["telemetry_type"], "live_metrics")
        self.assertEqual(msg["payload"]["rms"], 0.1)


class TestParseMessageDict(unittest.TestCase):
    def test_parses_valid_request(self):
        raw = make_request("ping", session_id=None, payload={})
        parsed = parse_message_dict(raw)
        self.assertEqual(parsed.message_type, "request")
        self.assertEqual(parsed.schema_version, SCHEMA_VERSION)

    def test_parses_valid_ack(self):
        parsed = parse_message_dict(make_ack("r1", session_id=None, payload={}))
        self.assertEqual(parsed.message_type, "ack")

    def test_parses_valid_error(self):
        parsed = parse_message_dict(make_error("r1", session_id=None, code="E", message="m"))
        self.assertEqual(parsed.message_type, "error")

    def test_parses_valid_telemetry(self):
        parsed = parse_message_dict(make_telemetry("live_metrics", session_id=None, payload={}))
        self.assertEqual(parsed.message_type, "telemetry")

    def test_rejects_wrong_schema_version(self):
        raw = make_request("ping", session_id=None, payload={})
        raw["schema_version"] = "calibration.v999"
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_rejects_unknown_message_type(self):
        raw = make_request("ping", session_id=None, payload={})
        raw["message_type"] = "unknown_type"
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_request_missing_required_field_raises(self):
        raw = make_request("ping", session_id=None, payload={})
        del raw["request_id"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_request_missing_action_raises(self):
        raw = make_request("ping", session_id=None, payload={})
        del raw["action"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_request_missing_payload_raises(self):
        raw = make_request("ping", session_id=None, payload={})
        del raw["payload"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_ack_missing_request_id_raises(self):
        raw = make_ack("r1", session_id=None, payload={})
        del raw["request_id"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_error_missing_error_field_raises(self):
        raw = make_error("r1", session_id=None, code="E", message="m")
        del raw["error"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_error_missing_error_code_raises(self):
        raw = make_error("r1", session_id=None, code="E", message="m")
        del raw["error"]["code"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)

    def test_telemetry_missing_telemetry_type_raises(self):
        raw = make_telemetry("live_metrics", session_id=None, payload={})
        del raw["telemetry_type"]
        with self.assertRaises(ProtocolError):
            parse_message_dict(raw)


class TestEncodeDecodeRoundtrip(unittest.TestCase):
    def test_encode_is_newline_terminated(self):
        raw = make_request("ping", session_id=None, payload={})
        encoded = encode_message(raw)
        self.assertTrue(encoded.endswith(b"\n"))

    def test_encode_is_valid_json(self):
        raw = make_request("ping", session_id=None, payload={"x": 1})
        encoded = encode_message(raw)
        decoded = json.loads(encoded.decode("utf-8").strip())
        self.assertEqual(decoded["action"], "ping")

    def test_decode_roundtrip(self):
        raw = make_request("open_session", session_id="s1", payload={"session_id": "s1"})
        encoded = encode_message(raw)
        line = encoded.rstrip(b"\n")
        parsed = decode_message(line)
        self.assertEqual(parsed.message_type, "request")
        self.assertEqual(parsed.raw["action"], "open_session")

    def test_decode_rejects_invalid_json(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"{not json}")

    def test_decode_rejects_non_object_json(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"[1,2,3]")


if __name__ == "__main__":
    unittest.main()
