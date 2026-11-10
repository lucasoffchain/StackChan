"""Launch Grok Build with temporary status hooks and a process heartbeat."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid

from monitor import write_state

EVENTS = (
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PostToolUseFailure", "Stop", "StopFailure", "StopCancelled",
    "Notification", "SessionEnd",
)
STATE_ENV = "STACKCHAN_MONITOR_STATE"
TOKEN_ENV = "STACKCHAN_MONITOR_TOKEN"
EVENT_LOG_ENV = "STACKCHAN_MONITOR_EVENT_LOG"


@contextmanager
def state_lock(path):
    """Serialize concurrent tool hooks without third-party dependencies."""
    with path.with_suffix(path.suffix + ".lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 1
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("status lock busy")
                time.sleep(0.01)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def reduce_event(current, event):
    """Only monitor the main session; ignore late reports for superseded turns."""
    if not isinstance(event, dict) or event.get("subagentType") or event.get("subagent_type"):
        return current
    name = event.get("hookEventName", event.get("hook_event_name", ""))
    name = str(name).replace("_", "").lower()
    if name not in {item.lower() for item in EVENTS}:
        return current
    result = dict(current)
    session = event.get("sessionId", event.get("session_id"))
    if name == "sessionstart":
        return {"state": "idle", "sessionId": session, "activeTools": [], "previousPrompts": []}
    if current.get("sessionId") and session and current["sessionId"] != session:
        return current
    if session:
        result["sessionId"] = session
    prompt = event.get("promptId")
    if prompt and prompt in current.get("previousPrompts", []):
        return current
    if prompt and prompt != current.get("promptId"):
        previous = list(current.get("previousPrompts", []))
        if current.get("promptId"):
            previous.append(current["promptId"])
        result.update(promptId=prompt, previousPrompts=previous[-20:], activeTools=[])
    tools = set(result.get("activeTools", []))
    tool = event.get("toolUseId", event.get("tool_use_id", "unknown"))
    if name == "userpromptsubmit":
        result.update(state="thinking", activeTools=[])
    elif name == "pretooluse":
        tools.add(tool)
        result.update(state="working", activeTools=sorted(tools))
    elif name in ("posttooluse", "posttoolusefailure"):
        tools.discard(tool)
        result.update(
            state="error" if name == "posttoolusefailure" else ("working" if tools else "thinking"),
            activeTools=sorted(tools),
        )
    elif name == "stop":
        if event.get("reason") != "end_turn":
            return current
        result.update(state="waiting" if event.get("backgroundTasks") or event.get("sessionCrons") else "done", activeTools=[])
    elif name == "stopfailure":
        result.update(state="error", activeTools=[])
    elif name == "stopcancelled":
        result.update(state="idle", activeTools=[])
    elif name == "sessionend":
        result.update(state="offline", activeTools=[])
    elif name == "notification":
        notification = event.get("notificationType")
        if notification == "permission_prompt":
            result["state"] = "waiting"
        elif notification == "idle_prompt" and result.get("state") in ("thinking", "working"):
            # Idle is a backstop, never proof that the turn succeeded.
            result.update(state="idle", activeTools=[])
        else:
            return current
    return result


def save_record(path, record):
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(record) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def handle_hook():
    # This is an observer: emit no stdout and never return a blocking exit code.
    if not os.environ.get(STATE_ENV) or not os.environ.get(TOKEN_ENV):
        return
    path = Path(os.environ[STATE_ENV])
    raw = sys.stdin.buffer.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        return
    event = json.loads(raw)
    with state_lock(path):
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("token") != os.environ[TOKEN_ENV]:
            return
        updated = reduce_event(current, event)
        if updated != current:
            updated["token"] = current["token"]
            save_record(path, updated)
        if os.environ.get(EVENT_LOG_ENV):
            # Record only lifecycle metadata, never prompts, commands or results.
            entry = {
                "time": time.time(),
                "event": event.get("hookEventName", event.get("hook_event_name")),
                "state": updated.get("state"),
                "changed": updated != current,
            }
            with Path(os.environ[EVENT_LOG_ENV]).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")


def quote_command(arguments, windows=None):
    windows = os.name == "nt" if windows is None else windows
    if windows:
        shell = os.environ.get("GROK_SHELL", "powershell").strip().lower()
        if shell in ("bash", "gitbash", "git-bash"):
            return shlex.join([value.replace("\\", "/") for value in arguments])
        if shell in ("cmd", "cmd.exe"):
            raise RuntimeError("For status hooks on Windows, set GROK_SHELL to powershell, pwsh or bash")
        # Grok's Windows hook shell is PowerShell. Literal arguments and & also
        # handle spaces/apostrophes in the Python executable or checkout path.
        return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in arguments)
    return shlex.join(arguments)


def hook_config(include_stop=True):
    command = quote_command([sys.executable, str(Path(__file__).resolve()), "hook"])
    return {"hooks": {
        event: [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}]
        for event in EVENTS if include_stop or event != "Stop"
    }}


def run_grok(args):
    command = args.grok_command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        command = ["grok"]
    path = args.status_file.resolve()
    if not path.parent.is_dir():
        raise RuntimeError(f"Status directory does not exist: {path.parent}")
    config = hook_config(include_stop=not args.no_stop_hook)
    hooks_dir = Path.cwd() / ".grok" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    hook_path = hooks_dir / f"stackchan-monitor-{token}.json"
    child = None
    owns_status = False
    exit_code = 1
    # Keep this lock for the whole launch, rejecting a second wrapper using the
    # same status file. Hook updates use the separate short-lived state lock.
    with state_lock(path.with_suffix(path.suffix + ".owner")):
        try:
            save_record(path, {"state": "unknown", "token": token})
            owns_status = True
            hook_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            environment = os.environ.copy()
            environment.update({STATE_ENV: str(path), TOKEN_ENV: token})
            if args.event_log:
                environment[EVENT_LOG_ENV] = str(args.event_log.resolve())
            print(f"StackChan status: {path}", file=sys.stderr)
            print("If hooks are disabled, use /hooks and /hooks-trust in Grok.", file=sys.stderr)
            # Inherit the real console so Grok's interactive TUI stays usable.
            child = subprocess.Popen(command, env=environment)
            while True:
                try:
                    exit_code = child.wait(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    path.touch(exist_ok=True)
                except KeyboardInterrupt:
                    # Grok receives the console interrupt too. Let it cancel the
                    # current turn; keep its heartbeat and monitor running.
                    continue
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            hook_path.unlink(missing_ok=True)
            if owns_status:
                with state_lock(path):
                    write_state(path, "offline" if exit_code == 0 else "error")
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hook", help="internal hook: consumes a Grok event on stdin")
    run = commands.add_parser("run", help="launch interactive Grok with status hooks")
    run.add_argument("--status-file", type=Path, default=Path(__file__).with_name("status.json"))
    run.add_argument("--no-stop-hook", action="store_true", help="use idle notifications when other Stop gates can continue the turn")
    run.add_argument("--event-log", type=Path, help="append lifecycle event names and status (no prompt or tool contents)")
    run.add_argument("grok_command", nargs=argparse.REMAINDER, help="-- grok [arguments]")
    args = parser.parse_args()
    if args.command == "hook":
        try:
            handle_hook()
        except Exception as exc:
            print(f"StackChan observer: {exc}", file=sys.stderr)
        return 0
    try:
        return run_grok(args)
    except (OSError, RuntimeError) as exc:
        print(f"StackChan launcher: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
