import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import grok_bridge as bridge


class EventTests(unittest.TestCase):
    def event(self, name, **fields):
        return {"hookEventName": name, "sessionId": "session", **fields}

    def test_full_turn_and_permission_wait(self):
        current = {"state": "unknown"}
        events = [
            (self.event("session_start"), "idle"),
            (self.event("user_prompt_submit", promptId="1"), "thinking"),
            (self.event("notification", notificationType="permission_prompt"), "waiting"),
            (self.event("pre_tool_use", promptId="1", toolUseId="tool"), "working"),
            (self.event("post_tool_use", promptId="1", toolUseId="tool"), "thinking"),
            (self.event("stop", promptId="1", reason="end_turn"), "done"),
            (self.event("notification", notificationType="idle_prompt"), "done"),
            (self.event("session_end"), "offline"),
        ]
        for event, state in events:
            current = bridge.reduce_event(current, event)
            self.assertEqual(current["state"], state)

    def test_idle_notification_never_turns_error_or_cancellation_into_success(self):
        for name, expected in (("stop_failure", "error"), ("stop_cancelled", "idle")):
            state = bridge.reduce_event({"state": "thinking"}, self.event(name))
            state = bridge.reduce_event(state, self.event("notification", notificationType="idle_prompt"))
            self.assertEqual(state["state"], expected)

    def test_parallel_tools_remain_working_until_last_finishes(self):
        current = {"state": "thinking"}
        for tool in ("a", "b"):
            current = bridge.reduce_event(current, self.event("pre_tool_use", toolUseId=tool))
        current = bridge.reduce_event(current, self.event("post_tool_use", toolUseId="a"))
        self.assertEqual(current["state"], "working")
        current = bridge.reduce_event(current, self.event("post_tool_use", toolUseId="b"))
        self.assertEqual(current["state"], "thinking")

    def test_late_cancel_for_old_turn_and_child_session_are_ignored(self):
        current = bridge.reduce_event({"state": "idle"}, self.event("user_prompt_submit", promptId="old"))
        current = bridge.reduce_event(current, self.event("user_prompt_submit", promptId="new"))
        self.assertEqual(bridge.reduce_event(current, self.event("stop_cancelled", promptId="old")), current)
        self.assertEqual(bridge.reduce_event(current, self.event("session_end", subagentType="explore")), current)
        self.assertEqual(bridge.reduce_event(current, {"hookEventName": "stop_failure", "sessionId": "other"}), current)

    def test_stop_with_background_work_is_waiting(self):
        event = self.event("stop", reason="end_turn", backgroundTasks=[{"type": "shell"}])
        self.assertEqual(bridge.reduce_event({"state": "working"}, event)["state"], "waiting")

    def test_compatibility_event_key_and_idle_backstop(self):
        current = bridge.reduce_event({"state": "idle"}, {"hook_event_name": "UserPromptSubmit"})
        self.assertEqual(current["state"], "thinking")
        current = bridge.reduce_event(current, self.event("notification", notificationType="idle_prompt"))
        self.assertEqual(current["state"], "idle")

    def test_stop_gate_compatibility_option(self):
        self.assertIn("Stop", bridge.hook_config()["hooks"])
        self.assertNotIn("Stop", bridge.hook_config(include_stop=False)["hooks"])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "status.json"

    def test_hook_stdin_updates_record_and_stays_silent(self):
        bridge.save_record(self.path, {"state": "idle", "token": "test"})
        environment = os.environ.copy()
        environment.update({bridge.STATE_ENV: str(self.path), bridge.TOKEN_ENV: "test"})
        event_log = self.directory / "events.jsonl"
        environment[bridge.EVENT_LOG_ENV] = str(event_log)
        result = subprocess.run(
            [sys.executable, bridge.__file__, "hook"],
            input=json.dumps({"hookEventName": "user_prompt_submit", "promptId": "1", "prompt": "PRIVATE PROMPT"}),
            text=True, capture_output=True, env=environment, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(self.path.read_text())["state"], "thinking")
        log_entry = json.loads(event_log.read_text())
        self.assertEqual(log_entry["event"], "user_prompt_submit")
        self.assertEqual(log_entry["state"], "thinking")
        self.assertNotIn("PRIVATE PROMPT", event_log.read_text())
        environment[bridge.TOKEN_ENV] = "wrong-run"
        subprocess.run(
            [sys.executable, bridge.__file__, "hook"], input='{"hookEventName":"stop_failure"}',
            text=True, capture_output=True, env=environment, check=True, timeout=10,
        )
        self.assertEqual(json.loads(self.path.read_text())["state"], "thinking")
        self.assertEqual(len(event_log.read_text().splitlines()), 1)

    @unittest.skipUnless(os.name == "nt", "Windows hook shell verification")
    def test_generated_hook_runs_via_powershell_with_json_stdin(self):
        bridge.save_record(self.path, {"state": "idle", "token": "shell-test"})
        environment = os.environ.copy()
        environment.update({bridge.STATE_ENV: str(self.path), bridge.TOKEN_ENV: "shell-test"})
        with patch.dict(os.environ, {"GROK_SHELL": "powershell"}):
            command = bridge.hook_config()["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            input='{"hookEventName":"user_prompt_submit","promptId":"shell"}',
            text=True, capture_output=True, env=environment, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(self.path.read_text())["state"], "thinking")

    def test_launcher_heartbeat_exit_status_and_temporary_hook_cleanup(self):
        fake = self.directory / "fake_grok.py"
        fake.write_text(
            "import json, os, pathlib, subprocess, sys, time\n"
            "state = pathlib.Path(os.environ['STACKCHAN_MONITOR_STATE'])\n"
            "hook = next(pathlib.Path('.grok/hooks').glob('stackchan-monitor-*.json'))\n"
            "assert 'PreToolUse' in json.loads(hook.read_text())['hooks']\n"
            "initial = state.stat().st_mtime\n"
            "time.sleep(2.5)\n"
            "assert state.stat().st_mtime > initial, 'heartbeat missing'\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, bridge.__file__, "run", "--status-file", str(self.path),
             "--", sys.executable, str(fake)],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.path.read_text())["state"], "offline")
        self.assertEqual(list((self.directory / ".grok/hooks").glob("*.json")), [])

    def test_failed_launch_records_error_and_cleans_hook(self):
        with patch("pathlib.Path.cwd", return_value=self.directory):
            args = argparse.Namespace(status_file=self.path, grok_command=[str(self.directory / "missing.exe")], no_stop_hook=False, event_log=None)
            with self.assertRaises(OSError):
                bridge.run_grok(args)
        self.assertEqual(json.loads(self.path.read_text())["state"], "error")
        self.assertEqual(list((self.directory / ".grok/hooks").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
