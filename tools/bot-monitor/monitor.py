"""Map local bot status to the existing StackChan DANCE BLE interface."""

import argparse
import asyncio
import json
import logging
import math
import os
from pathlib import Path
import struct
import time
import uuid

SERVICE_UUID = "e2e5e5e0-1234-5678-1234-56789abcdef0"
AVATAR_UUID = "e2e5e5e2-1234-5678-1234-56789abcdef0"
RGB_UUID = "e2e5e5e4-1234-5678-1234-56789abcdef0"
MAX_JSON_BYTES = 2048
# Color and a full pose: eye weight, rotation, size, x, y; mouth weight,
# rotation, x, y. Reset every field so a previous pose cannot leak through.
STYLES = {
    "unknown": ("#202020", (45, 0, 20, 0, 0), (45, 0, 20, 0, 0), (0, 0, 0, 0)),
    "idle": ("#003040", (100, 0, 0, 0, 0), (100, 0, 0, 0, 0), (0, 0, 0, 0)),
    "thinking": ("#303000", (40, 3350, 40, 55, -65), (100, 0, 75, 55, -65), (10, 3350, 35, 0)),
    "working": ("#001050", (100, 0, 100, 0, 0), (100, 0, 100, 0, 0), (100, 0, 0, 0)),
    "waiting": ("#301040", (40, 3200, 55, 0, -30), (90, 400, 55, 0, -30), (30, 0, 0, 0)),
    "done": ("#004000", (65, 1550, 100, 0, 0), (65, 2050, 100, 0, 0), (80, 0, 0, 0)),
    "error": ("#500000", (45, 450, 85, 0, 35), (45, 3150, 85, 0, 35), (0, 150, 0, 25)),
    "offline": ("#101010", (8, 0, 60, 0, 55), (8, 0, 60, 0, 55), (0, 0, 0, 20)),
}
STATUS_TEXT = {
    "en": dict(zip(STYLES, ("Grok: Unknown", "Grok: Ready", "Grok: Thinking...", "Grok: Working...",
                           "Grok: Needs attention", "Grok: Done!", "Grok: Error", "Grok: Offline"))),
    "zh": dict(zip(STYLES, ("状态未知", "准备就绪", "正在思考", "正在执行", "等待处理", "任务完成", "运行出错", "已离线"))),
}
LOG = logging.getLogger("stackchan-monitor")


def status_payloads(state, text_language=None, phase=None, skin=None):
    color, left, right, mouth = STYLES[state]
    def eye(values):
        weight, rotation, size, x, y = values
        return {"weight": weight, "rotation": rotation, "size": size, "x": x, "y": y}
    avatar = {
        "leftEye": eye(left),
        "rightEye": eye(right),
        "mouth": {"weight": mouth[0], "rotation": mouth[1], "x": mouth[2], "y": mouth[3]},
        "modifyLock": True,
    }
    if phase is not None:
        alternate = bool(phase % 2)
        direction = 100 if alternate else -100
        if state == "thinking":
            avatar["leftEye"].update(weight=100 if alternate else 0, x=direction, y=-100, size=100)
            avatar["rightEye"].update(weight=0 if alternate else 100, x=direction, y=-100, size=100)
            avatar["mouth"].update(weight=0, rotation=3300 if alternate else 300)
        elif state == "working":
            avatar["mouth"]["weight"] = 100 if alternate else 0
            for key in ("leftEye", "rightEye"):
                avatar[key].update(size=100, y=-70 if alternate else 70)
        elif state == "done":
            for key in ("leftEye", "rightEye"):
                avatar[key].update(weight=35, rotation=1800, size=100, y=-70 if alternate else 0)
            avatar["mouth"]["weight"] = 100 if alternate else 50
        elif state == "error":
            for key in ("leftEye", "rightEye"):
                avatar[key].update(x=direction, size=100)
            avatar["mouth"].update(x=direction, weight=60 if alternate else 0)
        elif state == "waiting":
            for key in ("leftEye", "rightEye"):
                avatar[key].update(x=direction, size=100)

    if text_language:
        avatar["title"] = "GROK"
        avatar["speech"] = STATUS_TEXT[text_language][state]
    if skin == "grok":
        avatar["monitor"] = {"skin": "grok", "state": state,
                             "text": STATUS_TEXT[text_language or "zh"][state].removeprefix("Grok: ")}
    elif skin == "default":
        avatar["monitor"] = {"skin": "default"}
    rgb = {"leftRgbColor": color, "rightRgbColor": color}
    return ((AVATAR_UUID, avatar), (RGB_UUID, rgb))


def fragment_json(value, payload_size=20):
    """Use the 10-byte AA 55 C3 v1 header from hal_ble.cpp, big endian."""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds the firmware's 2048-byte limit")
    if payload_size <= 10:
        raise ValueError("BLE payload must exceed the 10-byte fragment header")
    if len(raw) <= payload_size:
        return [raw]
    chunk_size = payload_size - 10
    count = math.ceil(len(raw) / chunk_size)
    return [
        struct.pack(">4sHHH", b"\xaa\x55\xc3\x01", index, count, len(raw))
        + raw[index * chunk_size : (index + 1) * chunk_size]
        for index in range(count)
    ]


def read_state(path, stale_after, now=None):
    """The producer must refresh the file even when its status is unchanged."""
    now = time.time() if now is None else now
    try:
        with path.open("rb") as stream:
            modified = os.fstat(stream.fileno()).st_mtime
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError("status file exceeds 4096 bytes")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("state") not in STYLES:
            raise ValueError("status file must contain a supported state")
        if now - modified > stale_after:
            return "offline", "status heartbeat expired"
        return data["state"], ""
    except (OSError, ValueError, TypeError):
        return "unknown", "status file missing, unreadable or invalid"


def write_state(path, state):
    """Publish atomically so the reader never observes half a JSON object."""
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps({"state": state}) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_bleak():
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:
        raise RuntimeError("Install BLE support: python -m pip install -r requirements.txt") from exc
    return BleakClient, BleakScanner


async def discover(scanner, timeout=8):
    results = await scanner.discover(timeout=timeout, service_uuids=[SERVICE_UUID])
    return sorted(results, key=lambda device: device.address)


async def write_json(client, characteristic, value):
    # Use the negotiated ATT MTU, retaining 20-byte compatibility when unknown.
    payload_size = min(max(getattr(client, "mtu_size", 23) - 3, 20), 512)
    for packet in fragment_json(value, payload_size):
        await client.write_gatt_char(characteristic, packet, response=True)


async def send_state(client, state, text_language=None, phase=None, skin=None):
    for characteristic, value in status_payloads(state, text_language, phase, skin):
        await write_json(client, characteristic, value)


async def show_state(address, state, text_language=None, skin=None):
    client_type, _ = load_bleak()
    async with client_type(address, timeout=15) as client:
        await send_state(client, state, text_language, skin=skin)
        LOG.info("BLE writes acknowledged: %s, state=%s", client.address, state)


async def expression_demo(address, hold):
    """Send avatar poses only: keep the LEDs unchanged to inspect the face."""
    client_type, _ = load_bleak()
    async with client_type(address, timeout=15) as client:
        try:
            LOG.info("Negotiated ATT MTU: %s", getattr(client, "mtu_size", 23))
            for state in ("offline", "thinking", "working", "done", "error", "idle"):
                LOG.info("Showing animated face: %s (%.1fs)", state, hold)
                until = time.monotonic() + hold
                phase = 0
                while time.monotonic() < until:
                    _, avatar = status_payloads(state, phase=phase)[0]
                    await write_json(client, AVATAR_UUID, avatar)
                    phase += 1
                    await asyncio.sleep(0.8)
        finally:
            if client.is_connected:
                # Release modifier ownership on updated firmware after the demo.
                await write_json(client, AVATAR_UUID, {"modifyLock": False})


async def monitor(args):
    client_type = scanner = None
    if not args.dry_run:
        client_type, scanner = load_bleak()
    started = time.monotonic()
    client = None
    last_sent = None
    last_frame = None
    last_reported = None
    sent_at = 0.0
    retry_at = 0.0
    try:
        while True:
            now = time.monotonic()
            if args.demo:
                states = list(STYLES)
                state = states[int((now - started) / 3) % len(states)]
                reason = "demo"
            else:
                state, reason = read_state(args.status_file, args.stale_after)
            phase = None if args.static_face or args.skin == "grok" or state not in ("thinking", "working", "done", "error", "waiting") else int(now - started) % 2
            if (state, reason) != last_reported:
                LOG.info("Bot: %s%s", state, f" ({reason})" if reason else "")
                last_reported = (state, reason)
            if args.dry_run:
                if (state, phase) != last_frame:
                    print(json.dumps(dict(status_payloads(state, args.text, phase, args.skin)), ensure_ascii=False), flush=True)
                    last_sent = state
                    last_frame = (state, phase)
            elif now >= retry_at:
                try:
                    if client is None or not client.is_connected:
                        if client is not None:
                            await client.disconnect()
                            client = None
                        device = args.address
                        if not device:
                            devices = await discover(scanner)
                            if len(devices) != 1:
                                raise RuntimeError(
                                    f"Found {len(devices)} StackChan devices; run scan and pass --address"
                                )
                            device = devices[0]
                        client = client_type(device, timeout=15)
                        await client.connect()
                        for characteristic, _ in status_payloads(state):
                            if client.services.get_characteristic(characteristic) is None:
                                raise RuntimeError("Missing StackChan characteristics; open DANCE on the robot")
                        LOG.info("BLE connected: %s", client.address)
                        # Re-read status after connection/scanning delays.
                        last_sent = None
                        continue
                    if state != last_sent or (state, phase) != last_frame or now - sent_at >= 5:
                        await send_state(client, state, args.text, phase, args.skin)
                        if state != last_sent:
                            LOG.info("BLE writes acknowledged: state=%s", state)
                        last_sent, sent_at = state, time.monotonic()
                        last_frame = (state, phase)
                except Exception as exc:
                    LOG.warning("BLE unavailable: %s; retrying in 3 seconds", exc)
                    if client is not None:
                        try:
                            await client.disconnect()
                        except Exception:
                            LOG.debug("Disconnect failed", exc_info=True)
                    client = None
                    last_sent = None
                    retry_at = time.monotonic() + 3
            await asyncio.sleep(0.5)
    finally:
        if client is not None:
            try:
                if client.is_connected:
                    await write_json(client, AVATAR_UUID, {"modifyLock": False})
                await client.disconnect()
            except Exception:
                LOG.debug("Disconnect failed during shutdown", exc_info=True)


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan", help="list nearby StackChan BLE devices")
    show = commands.add_parser("show", help="connect and send one status, then disconnect")
    show.add_argument("state", choices=STYLES)
    show.add_argument("--address", required=True)
    show.add_argument("--text", choices=STATUS_TEXT, help="requires updated firmware; zh also requires a CJK font")
    show.add_argument("--skin", choices=("grok", "default"), help="requires updated firmware; grok includes Chinese status text by default")
    faces = commands.add_parser("expressions", help="demonstrate six faces without changing RGB lights")
    faces.add_argument("--address", required=True)
    faces.add_argument("--hold", type=positive_seconds, default=5, help="seconds to show each expression")
    run = commands.add_parser("monitor", help="display bot status on StackChan")
    run.add_argument("--address", help="address from scan; required if multiple devices are nearby")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--status-file", type=Path)
    source.add_argument("--demo", action="store_true", help="cycle simulated statuses every 3 seconds")
    run.add_argument("--stale-after", type=positive_seconds, default=30, help="heartbeat expiry in seconds (default: 30)")
    run.add_argument("--dry-run", action="store_true", help="print BLE JSON without using Bluetooth")
    run.add_argument("--text", choices=STATUS_TEXT, help="requires updated firmware; zh also requires a CJK font")
    run.add_argument("--skin", choices=("grok", "default"), help="requires updated firmware; grok animates locally on the robot")
    run.add_argument("--static-face", action="store_true", help="disable repeated facial animation")
    publish = commands.add_parser("publish", help="atomically update the local status file")
    publish.add_argument("status_file", type=Path)
    publish.add_argument("state", choices=STYLES)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.command == "publish":
            write_state(args.status_file, args.state)
        elif args.command == "show":
            asyncio.run(show_state(args.address, args.state, args.text, args.skin))
        elif args.command == "expressions":
            asyncio.run(expression_demo(args.address, args.hold))
        elif args.command == "scan":
            _, scanner = load_bleak()
            devices = asyncio.run(discover(scanner))
            for device in devices:
                print(f"{device.address}\t{device.name or 'StackChan'}")
            if not devices:
                LOG.info("No StackChan found. Enable Bluetooth and open DANCE on the robot.")
        else:
            asyncio.run(monitor(args))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
