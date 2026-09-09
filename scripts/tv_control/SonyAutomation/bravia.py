#!/usr/bin/env python3
"""
Sony Bravia BF1 Remote Control (Simple IP Protocol / SSIP)
===========================================================
Controls Sony Bravia professional displays over the Simple IP Protocol.
TCP port 20060, fixed 24-byte ASCII messages, no authentication.

Setup on TV:
  Settings → Network & Internet → Home network → IP control →
            Simple IP control: ON
  Settings → Network & Internet → Remote device settings →
            Control remotely: ON   (for Wake-on-LAN)

Zero external dependencies — uses only Python stdlib.

Usage:
    python bravia.py <command> [args]
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

# ─── Configuration ──────────────────────────────────────────────────────────

TV_IP = "192.168.14.133"           # Update to your BF1's IP
TV_PORT = 20060                  # SSIP fixed port
TV_MAC = "58:18:62:30:2F:EB"     # Get from TV: View Network Status

REQUEST_TIMEOUT = 5              # Per-socket TCP timeout in seconds


# ─── SSIP Protocol Constants ────────────────────────────────────────────────
# Each message is exactly 24 bytes:
#   [0-1] Header  : "*S"          (0x2A 0x53)
#   [2]   Type    : C/E/A/N
#   [3-6] Command : 4 ASCII chars
#   [7-22]Param   : 16 ASCII chars (or # for enquiry padding)
#   [23]  Footer  : LF (0x0A)

ENQ_PARAM = "#" * 16             # Used in Enquiry messages
SUCCESS_PARAM = "0" * 16         # Answer-Success
ERROR_PARAM = "F" * 16           # Answer-Error
NOT_FOUND_PARAM = "N" * 16       # Answer-Not-Found (e.g. setInput to missing port)


# ─── IR Commands (used with setIrccCode) ───────────────────────────────────
# Source: pro-bravia.sony.net Simple IP control spec.
# Each parameter is right-aligned numeric padded with zeros to 16 chars.

IRCC_PARAMS = {
    # Navigation
    "display":      "0000000000000005",
    "home":         "0000000000000006",
    "options":      "0000000000000007",
    "return":       "0000000000000008",
    "back":         "0000000000000008",   # alias for return
    "up":           "0000000000000009",
    "down":         "0000000000000010",
    "right":        "0000000000000011",
    "left":         "0000000000000012",
    "confirm":      "0000000000000013",
    "ok":           "0000000000000013",   # alias for confirm
    "center":       "0000000000000013",   # alias for confirm

    # Color buttons
    "red":          "0000000000000014",
    "green":        "0000000000000015",
    "yellow":       "0000000000000016",
    "blue":         "0000000000000017",

    # Numbers
    "num1":         "0000000000000018",
    "num2":         "0000000000000019",
    "num3":         "0000000000000020",
    "num4":         "0000000000000021",
    "num5":         "0000000000000022",
    "num6":         "0000000000000023",
    "num7":         "0000000000000024",
    "num8":         "0000000000000025",
    "num9":         "0000000000000026",
    "num0":         "0000000000000027",

    # Audio / volume
    "vol_up":       "0000000000000030",
    "vol_down":     "0000000000000031",
    "mute":         "0000000000000032",

    # Channel
    "ch_up":        "0000000000000033",
    "ch_down":      "0000000000000034",

    # Misc
    "subtitle":     "0000000000000035",
    "dot":          "0000000000000038",
    "picture_off":  "0000000000000050",
    "wide":         "0000000000000061",
    "jump":         "0000000000000062",
    "sync_menu":    "0000000000000076",

    # Transport
    "forward":      "0000000000000077",
    "ff":           "0000000000000077",   # alias
    "play":         "0000000000000078",
    "rewind":       "0000000000000079",
    "prev":         "0000000000000080",
    "stop":         "0000000000000081",
    "next":         "0000000000000082",
    "pause":        "0000000000000084",
    "flash_plus":   "0000000000000086",
    "flash_minus":  "0000000000000087",

    # Power / system
    "tv_power":     "0000000000000098",
    "audio":        "0000000000000099",
    "input":        "0000000000000101",
    "sleep":        "0000000000000104",
    "sleep_timer":  "0000000000000105",
    "video2":       "0000000000000108",
    "picture_mode": "0000000000000110",
    "demo_surround": "0000000000000121",

    # Inputs (direct HDMI selection)
    "hdmi1":        "0000000000000124",
    "hdmi2":        "0000000000000125",
    "hdmi3":        "0000000000000126",
    "hdmi4":        "0000000000000127",

    # Menus
    "action_menu":  "0000000000000129",
    "menu":         "0000000000000129",   # alias
    "help":         "0000000000000130",
}


# ─── Wake-on-LAN ────────────────────────────────────────────────────────────

def send_wol(mac: str, broadcast: str = "255.255.255.255", port: int = 9):
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(magic, (broadcast, port))


# ─── SSIP Transport ─────────────────────────────────────────────────────────

def _build_msg(msg_type: str, command: str, parameter: str) -> bytes:
    """Build a 24-byte SSIP message."""
    if len(command) != 4:
        raise ValueError(f"command must be 4 chars, got {command!r}")
    if len(parameter) != 16:
        raise ValueError(f"parameter must be 16 chars, got {parameter!r}")
    if msg_type not in ("C", "E", "A", "N"):
        raise ValueError(f"msg_type must be C/E/A/N, got {msg_type!r}")
    msg = f"*S{msg_type}{command}{parameter}\n".encode("ascii")
    assert len(msg) == 24, f"built msg has wrong length: {len(msg)}"
    return msg


def _parse_msg(raw: bytes) -> tuple[str, str, str] | None:
    """Parse a 24-byte SSIP message → (type, command, parameter), or None."""
    if len(raw) < 24:
        return None
    if raw[0:2] != b"*S":
        return None
    msg_type = chr(raw[2])
    command = raw[3:7].decode("ascii", errors="replace")
    parameter = raw[7:23].decode("ascii", errors="replace")
    return (msg_type, command, parameter)


def ssip_send(msg_type: str, command: str, parameter: str,
              expect_command: str | None = None) -> tuple[str, str, str] | None:
    """Send a SSIP message, return the first matching Answer (A) reply.
    Notify (N) messages are skipped. Returns (type, command, param) or None."""
    payload = _build_msg(msg_type, command, parameter)

    try:
        with socket.create_connection((TV_IP, TV_PORT), timeout=REQUEST_TIMEOUT) as s:
            s.sendall(payload)

            # Read responses, skipping any Notify (N) messages
            buf = b""
            deadline = time.monotonic() + REQUEST_TIMEOUT
            target_cmd = expect_command or command

            while time.monotonic() < deadline:
                try:
                    s.settimeout(max(0.1, deadline - time.monotonic()))
                    chunk = s.recv(256)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf += chunk

                # Process full 24-byte messages
                while len(buf) >= 24:
                    msg = buf[:24]
                    buf = buf[24:]
                    parsed = _parse_msg(msg)
                    if parsed is None:
                        continue
                    mtype, mcmd, mparam = parsed
                    # Skip Notify messages
                    if mtype == "N":
                        continue
                    # Return the matching Answer
                    if mtype == "A" and mcmd == target_cmd:
                        return parsed
                    # Any other Answer: return it (may be relevant)
                    if mtype == "A":
                        return parsed
            return None
    except OSError as e:
        print(f"⚠️  Connection refused: {e}")
        return None


def _is_success(parsed) -> bool:
    if parsed is None:
        return False
    return parsed[2] == SUCCESS_PARAM


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_on(_args):
    """Wake TV via WoL, then send setPowerStatus active."""
    if TV_MAC != "XX:XX:XX:XX:XX:XX":
        print(f"📡 Sending Wake-on-LAN to {TV_MAC}...")
        for _ in range(4):
            send_wol(TV_MAC, broadcast="192.168.14.255")
            time.sleep(0.5)
        print("✅ WoL packets sent.")
        # Give the TV time to bring its TCP server up
        time.sleep(2)

    parsed = ssip_send("C", "POWR", "0000000000000001")
    if _is_success(parsed):
        print("⚡ Power on accepted.")
    elif parsed is None:
        print("⚠️  No answer (TV may still be booting; retry in a few seconds).")
    else:
        print(f"⚠️  Power on response: {parsed}")


def cmd_off(_args):
    parsed = ssip_send("C", "POWR", "0000000000000000")
    if _is_success(parsed):
        print("📴 Power off accepted.")
    elif parsed is None:
        print("⚠️  No answer (TV may already be off).")
    else:
        print(f"⚠️  Power off response: {parsed}")


def cmd_power_state(_args):
    parsed = ssip_send("E", "POWR", ENQ_PARAM)
    if parsed is None:
        print("📴 No answer (TV likely off / TCP server not running).")
        return
    _, _, param = parsed
    if param == SUCCESS_PARAM:
        print("⚡ Power state: STANDBY (off)")
    elif param == "0" * 15 + "1":
        print("⚡ Power state: ACTIVE (on)")
    elif param == ERROR_PARAM:
        print("⚠️  Power state: error response")
    else:
        print(f"⚡ Power state: param={param}")


def cmd_toggle_power(_args):
    parsed = ssip_send("C", "TPOW", ENQ_PARAM)
    if _is_success(parsed):
        print("⚡ Power toggled.")
    else:
        print(f"⚠️  Toggle response: {parsed}")


def cmd_status(_args):
    print(f"🔍 Checking {TV_IP}:{TV_PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        result = s.connect_ex((TV_IP, TV_PORT))
        if result == 0:
            print("✅ SSIP server is reachable (TV is ON).")
            cmd_power_state(_args)
        else:
            print("📴 TV appears to be OFF or unreachable.")
            print("   Run 'on' to wake via WoL, then wait ~10-20s.")
    finally:
        s.close()


def cmd_key(args):
    """Send an IRCC IR-style key code via setIrccCode."""
    name = args.key.lower().replace("-", "_")
    param = IRCC_PARAMS.get(name)
    if param is None:
        print(f"❌ Unknown key '{args.key}'")
        print(f"   Run 'keys' to see available keys.")
        sys.exit(1)
    parsed = ssip_send("C", "IRCC", param, expect_command="IRCC")
    if _is_success(parsed):
        print(f"🎮 Key: {name}")
    elif parsed is None:
        print(f"⚠️  Key '{name}' got no answer (timeout or refused)")
        sys.exit(1)
    else:
        print(f"⚠️  Key '{name}' response: {parsed}")


def cmd_keys(_args):
    print("Available remote keys (case-insensitive, '-' or '_' interchangeable):")
    for name in sorted(IRCC_PARAMS.keys()):
        print(f"  {name}")


def cmd_set_input(args):
    """Switch input via setInput. Accepts 'hdmi1', 'hdmi2', etc.,
    or raw 8-digit type+port code."""
    spec = args.input_uri.lower().strip()
    if spec.startswith("hdmi"):
        port_str = "".join(c for c in spec if c.isdigit()) or "1"
        port = int(port_str)
        # Type 1 = HDMI; param = "0000000" + type + "0000" + port (4 digits)
        param = f"00000001{port:04d}".rjust(16, "0")
        # Spec format: "0000000{type:1}0000{port:4}" → 16 chars total
        param = f"0000000{1}0000{port:04d}"
        if len(param) != 16:
            print(f"⚠️  Built bad parameter: {param!r}")
            sys.exit(1)
    elif len(spec) == 16 and all(c in "0123456789" for c in spec):
        param = spec
    else:
        print(f"❌ Unknown input '{args.input_uri}'")
        print("   Use 'hdmi1'..'hdmi4', or a raw 16-digit input code.")
        sys.exit(1)

    parsed = ssip_send("C", "INPT", param)
    if _is_success(parsed):
        print(f"📺 Input → {spec}")
    elif parsed and parsed[2] == NOT_FOUND_PARAM:
        print(f"⚠️  Input not found: {spec}")
        sys.exit(1)
    elif parsed is None:
        print("⚠️  No answer.")
        sys.exit(1)
    else:
        print(f"⚠️  Set-input response: {parsed}")


def cmd_get_input(_args):
    parsed = ssip_send("E", "INPT", ENQ_PARAM)
    if parsed is None:
        print("📴 No answer.")
        return
    _, _, param = parsed
    print(f"📺 Current input param: {param}")


def cmd_volume(args):
    val = max(0, min(100, int(args.value)))
    param = f"{val:016d}"
    parsed = ssip_send("C", "VOLU", param)
    if _is_success(parsed):
        print(f"🔊 Volume → {val}")
    else:
        print(f"⚠️  Volume response: {parsed}")


def cmd_mute(args):
    if args.state == "on":
        param = "0" * 15 + "1"
    elif args.state == "off":
        param = "0" * 16
    else:
        print("❌ mute requires 'on' or 'off'")
        sys.exit(1)
    parsed = ssip_send("C", "AMUT", param)
    if _is_success(parsed):
        print(f"🔇 Mute {args.state}")
    else:
        print(f"⚠️  Mute response: {parsed}")


def cmd_picture_mute(args):
    if args.state == "on":
        param = "0" * 15 + "1"
    elif args.state == "off":
        param = "0" * 16
    elif args.state == "toggle":
        parsed = ssip_send("C", "TPMU", ENQ_PARAM)
        if _is_success(parsed):
            print("🖥  Picture mute toggled.")
        else:
            print(f"⚠️  Picture-mute response: {parsed}")
        return
    else:
        print("❌ picture-mute requires on/off/toggle")
        sys.exit(1)
    parsed = ssip_send("C", "PMUT", param)
    if _is_success(parsed):
        print(f"🖥  Picture mute {args.state}")
    else:
        print(f"⚠️  Picture-mute response: {parsed}")


def cmd_raw(args):
    """Send a raw SSIP command. Format: TYPE COMMAND PARAM
    e.g. 'raw C POWR 0000000000000001' """
    parsed = ssip_send(args.msg_type, args.command, args.parameter)
    print(f"Reply: {parsed}")


def cmd_mac(_args):
    parsed = ssip_send("E", "MADR", "eth0############")
    if parsed is None:
        print("⚠️  No answer.")
        return
    _, _, param = parsed
    if param == ERROR_PARAM:
        print("⚠️  Error reply (interface not found?).")
        return
    mac = param.rstrip("#")
    print(f"MAC: {mac}")


def cmd_broadcast(_args):
    parsed = ssip_send("E", "BADR", "eth0############")
    if parsed is None:
        print("⚠️  No answer.")
        return
    _, _, param = parsed
    if param == ERROR_PARAM:
        print("⚠️  Error reply.")
        return
    addr = param.rstrip("#")
    print(f"Broadcast: {addr}")


# ─── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bravia",
        description="Sony Bravia BF1 Remote (Simple IP Protocol on TCP 20060)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("on", help="Wake TV (WoL + power on)").set_defaults(func=cmd_on)
    sub.add_parser("off", help="Power off TV").set_defaults(func=cmd_off)
    sub.add_parser("toggle-power", help="Toggle power").set_defaults(func=cmd_toggle_power)
    sub.add_parser("power-state", help="Get power state").set_defaults(func=cmd_power_state)
    sub.add_parser("status", help="Reachability + power state").set_defaults(func=cmd_status)

    k = sub.add_parser("key", help="Press a remote key (IRCC via SSIP)")
    k.add_argument("key", help="Key name (run 'keys' to list)")
    k.set_defaults(func=cmd_key)

    sub.add_parser("keys", help="List remote keys").set_defaults(func=cmd_keys)

    si = sub.add_parser("set-input", help="Switch input")
    si.add_argument("input_uri", help="hdmi1 / hdmi2 / hdmi3 / hdmi4")
    si.set_defaults(func=cmd_set_input)

    sub.add_parser("get-input", help="Get current input").set_defaults(func=cmd_get_input)

    v = sub.add_parser("volume", help="Set volume (0-100)")
    v.add_argument("value", help="Integer 0-100")
    v.set_defaults(func=cmd_volume)

    m = sub.add_parser("mute", help="Mute on/off")
    m.add_argument("state", choices=["on", "off"])
    m.set_defaults(func=cmd_mute)

    pm = sub.add_parser("picture-mute", help="Picture mute on/off/toggle (screen black)")
    pm.add_argument("state", choices=["on", "off", "toggle"])
    pm.set_defaults(func=cmd_picture_mute)

    sub.add_parser("mac", help="Get TV's MAC address (eth0)").set_defaults(func=cmd_mac)
    sub.add_parser("broadcast", help="Get broadcast address (eth0)").set_defaults(func=cmd_broadcast)

    r = sub.add_parser("raw", help="Send a raw SSIP command")
    r.add_argument("msg_type", choices=["C", "E"])
    r.add_argument("command", help="4-letter SSIP command (e.g. POWR, IRCC)")
    r.add_argument("parameter", help="16-character parameter")
    r.set_defaults(func=cmd_raw)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
