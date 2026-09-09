#!/usr/bin/env python3
"""
Sony Bravia REST API Remote Control
=====================================
Controls Sony Bravia consumer/Google TV displays over the REST API.
HTTP port 80, JSON-RPC style, authenticated via Pre-Shared Key (PSK).

Tested on: KD-32W830K and similar consumer Bravia / Google TV models.
(For professional BF1 displays using SSIP/TCP 20060, use the original script.)

Setup on TV:
  Settings → Device Preferences → IP control → Simple IP control: ON
  Settings → Device Preferences → IP control → Pre-Shared Key: set to e.g. 0000
  Settings → Device Preferences → About → Remote device settings →
            Control remotely: ON   (for Wake-on-LAN)

Requires: requests  (pip install requests)

Usage:
    python bravia.py <command> [args]
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

try:
    import requests
except ImportError:
    print("❌ Missing dependency: pip install requests")
    sys.exit(1)

# ─── Configuration ──────────────────────────────────────────────────────────

TV_IP   = "192.168.14.140"        # Update to your TV's IP
TV_MAC  = "88:C9:E8:78:BE:7B"    # From TV or curl getSystemInformation
TV_PSK  = "0000"                  # Pre-Shared Key set on the TV

REQUEST_TIMEOUT = 5               # HTTP timeout in seconds


# ─── IRCC key codes (base64-encoded) ────────────────────────────────────────
# Source: Sony Bravia REST API / IRCC spec.

IRCC_CODES = {
    # Power — from getRemoteControllerInfo
    "power":            "AAAAAQAAAAEAAAAvAw==",  # PowerOff
    "tv_power":         "AAAAAQAAAAEAAAAVAw==",  # TvPower (toggle)
    "wake":             "AAAAAQAAAAEAAAAuAw==",  # WakeUp
    "sleep":            "AAAAAQAAAAEAAAAvAw==",  # Sleep

    # Navigation — use Cursor* variants for Google TV UI
    "up":               "AAAAAgAAAJcAAABPAw==",  # CursorUp
    "down":             "AAAAAgAAAJcAAABQAw==",  # CursorDown
    "left":             "AAAAAgAAAJcAAABNAw==",  # CursorLeft
    "right":            "AAAAAgAAAJcAAABOAw==",  # CursorRight
    "confirm":          "AAAAAgAAAJcAAABKAw==",  # DpadCenter
    "ok":               "AAAAAgAAAJcAAABKAw==",  # alias
    "home":             "AAAAAQAAAAEAAABgAw==",  # Home
    "return":           "AAAAAgAAAJcAAAAjAw==",  # Return
    "back":             "AAAAAgAAAJcAAAAjAw==",  # alias
    "options":          "AAAAAgAAAJcAAAA2Aw==",  # Options
    "action_menu":      "AAAAAgAAAMQAAABLAw==",  # ActionMenu
    "display":          "AAAAAQAAAAEAAAA6Aw==",  # Display
    "exit":             "AAAAAQAAAAEAAABjAw==",  # Exit
    "help":             "AAAAAgAAAMQAAABNAw==",  # Help

    # Numbers
    "num1":             "AAAAAQAAAAEAAAAAAw==",
    "num2":             "AAAAAQAAAAEAAAABAw==",
    "num3":             "AAAAAQAAAAEAAAACAw==",
    "num4":             "AAAAAQAAAAEAAAADAw==",
    "num5":             "AAAAAQAAAAEAAAAEAw==",
    "num6":             "AAAAAQAAAAEAAAAFAw==",
    "num7":             "AAAAAQAAAAEAAAAGAw==",
    "num8":             "AAAAAQAAAAEAAAAHAw==",
    "num9":             "AAAAAQAAAAEAAAAIAw==",
    "num0":             "AAAAAQAAAAEAAAAJAw==",
    "dot":              "AAAAAgAAAJcAAAAdAw==",  # DOT

    # Volume / audio
    "vol_up":           "AAAAAQAAAAEAAAASAw==",
    "vol_down":         "AAAAAQAAAAEAAAATAw==",
    "mute":             "AAAAAQAAAAEAAAAUAw==",
    "audio":            "AAAAAQAAAAEAAAAXAw==",  # MediaAudioTrack

    # Channel
    "ch_up":            "AAAAAQAAAAEAAAAQAw==",
    "ch_down":          "AAAAAQAAAAEAAAARAw==",

    # Color buttons
    "red":              "AAAAAgAAAJcAAAAlAw==",
    "green":            "AAAAAgAAAJcAAAAmAw==",
    "yellow":           "AAAAAgAAAJcAAAAnAw==",
    "blue":             "AAAAAgAAAJcAAAAkAw==",

    # Transport
    "play":             "AAAAAgAAAJcAAAAaAw==",
    "pause":            "AAAAAgAAAJcAAAAZAw==",
    "stop":             "AAAAAgAAAJcAAAAYAw==",
    "ff":               "AAAAAgAAAJcAAAAcAw==",
    "forward":          "AAAAAgAAAJcAAAAcAw==",  # alias
    "rewind":           "AAAAAgAAAJcAAAAbAw==",
    "next":             "AAAAAgAAAJcAAAA9Aw==",
    "prev":             "AAAAAgAAAJcAAAA8Aw==",
    "rec":              "AAAAAgAAAJcAAAAgAw==",

    # Inputs
    "input":            "AAAAAQAAAAEAAAAlAw==",  # TvInput
    "tv":               "AAAAAQAAAAEAAAAkAw==",  # Tv
    "hdmi1":            "AAAAAgAAABoAAABaAw==",
    "hdmi2":            "AAAAAgAAABoAAABbAw==",
    "hdmi3":            "AAAAAgAAABoAAABcAw==",

    # Apps
    "netflix":          "AAAAAgAAABoAAAB8Aw==",
    "youtube":          "AAAAAgAAAMQAAABHAw==",
    "google_play":      "AAAAAgAAAMQAAABGAw==",
    "app_launcher":     "AAAAAgAAAMQAAAAqAw==",

    # Misc
    "subtitle":         "AAAAAgAAAJcAAAAoAw==",
    "epg":              "AAAAAgAAAKQAAABbAw==",
    "teletext":         "AAAAAQAAAAEAAAA/Aw==",
    "jump":             "AAAAAQAAAAEAAAA7Aw==",
}


# ─── Wake-on-LAN ────────────────────────────────────────────────────────────

def send_wol(mac: str, broadcast: str = "255.255.255.255", port: int = 9):
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(magic, (broadcast, port))


# ─── REST Transport ─────────────────────────────────────────────────────────

def sony_call(service: str, method: str, params: list = [],
              version: str = "1.0") -> dict | None:
    """POST a JSON-RPC call to the TV. Returns the full response dict or None."""
    url = f"http://{TV_IP}/sony/{service}"
    headers = {"X-Auth-PSK": TV_PSK, "Content-Type": "application/json"}
    payload = {"method": method, "params": params, "id": 1, "version": version}
    try:
        r = requests.post(url, json=payload, headers=headers,
                          timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"⚠️  Connection refused — is the TV on and IP control enabled?")
        return None
    except requests.exceptions.Timeout:
        print(f"⚠️  Request timed out.")
        return None
    except Exception as e:
        print(f"⚠️  Request error: {e}")
        return None


def sony_ircc(code: str) -> bool:
    """Send an IRCC key code via SOAP (required on KD-32W830K and similar)."""
    url = f"http://{TV_IP}/sony/ircc"
    headers = {
        "X-Auth-PSK": TV_PSK,
        "Content-Type": "text/xml",
        "SOAPAction": '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"',
    }
    body = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
        ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        '<u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1">'
        f"<IRCCCode>{code}</IRCCCode>"
        "</u:X_SendIRCC>"
        "</s:Body>"
        "</s:Envelope>"
    )
    try:
        r = requests.post(url, data=body, headers=headers, timeout=REQUEST_TIMEOUT)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        print("⚠️  Connection refused — is the TV on and IP control enabled?")
        return False
    except requests.exceptions.Timeout:
        print("⚠️  Request timed out.")
        return False
    except Exception as e:
        print(f"⚠️  IRCC error: {e}")
        return False


def _get_result(resp: dict | None) -> dict | list | None:
    """Extract result from response, printing any error."""
    if resp is None:
        return None
    if "error" in resp:
        code, msg = resp["error"][0], resp["error"][1]
        print(f"⚠️  API error {code}: {msg}")
        return None
    results = resp.get("result", [])
    return results[0] if results else {}   # empty list = success with no payload


def _is_success(resp: dict | None) -> bool:
    if resp is None:
        return False
    if "error" in resp:
        return False
    return "result" in resp


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_on(_args):
    # TvPower is a toggle — safe because SonyAutomation checks state first
    if sony_ircc(IRCC_CODES["tv_power"]):
        print("⚡ Power on sent.")
    else:
        print("⚠️  No answer — TV may be fully off (no network standby).")


def cmd_off(_args):
    # TvPower is a toggle — safe because SonyAutomation checks state first
    if sony_ircc(IRCC_CODES["tv_power"]):
        print("📴 Power off sent.")
    else:
        print("⚠️  No answer (TV may already be off).")


def cmd_power_state(_args):
    resp = sony_call("system", "getPowerStatus")
    result = _get_result(resp)
    if result is None:
        print("📴 No answer (TV likely off).")
        return
    status = result.get("status", "unknown")
    icon = "⚡" if status == "active" else "📴"
    print(f"{icon} Power state: {status.upper()}")


def cmd_status(_args):
    print(f"🔍 Checking {TV_IP}:80...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        result = s.connect_ex((TV_IP, 80))
        if result == 0:
            print("✅ REST API server is reachable (TV is ON).")
            cmd_power_state(_args)
        else:
            print("📴 TV appears to be OFF or unreachable.")
            print("   Run 'on' to wake via WoL, then wait ~10-20s.")
    finally:
        s.close()

def cmd_key(args):
    name = args.key.lower().replace("-", "_")
    code = IRCC_CODES.get(name)
    if code is None:
        print(f"❌ Unknown key '{args.key}'")
        print(f"   Run 'keys' to see available keys.")
        sys.exit(1)
    if sony_ircc(code):
        print(f"🎮 Key: {name}")
    else:
        print(f"⚠️  Key '{name}' got no answer.")
        sys.exit(1)


def cmd_keys(_args):
    print("Available remote keys (case-insensitive, '-' or '_' interchangeable):")
    for name in sorted(IRCC_CODES.keys()):
        print(f"  {name}")


def cmd_set_input(args):
    spec = args.input_uri.lower().strip()
    if spec.startswith("hdmi"):
        port_str = "".join(c for c in spec if c.isdigit()) or "1"
        uri = f"extInput:hdmi?port={port_str}"
    elif spec.startswith("component"):
        port_str = "".join(c for c in spec if c.isdigit()) or "1"
        uri = f"extInput:component?port={port_str}"
    elif spec.startswith("composite") or spec.startswith("av"):
        port_str = "".join(c for c in spec if c.isdigit()) or "1"
        uri = f"extInput:composite?port={port_str}"
    elif spec.startswith("extinput:"):
        uri = spec  # raw URI passthrough
    else:
        print(f"❌ Unknown input '{args.input_uri}'")
        print("   Use: hdmi1..hdmi4, component1, composite1, or extInput:hdmi?port=1")
        sys.exit(1)

    resp = sony_call("avContent", "setPlayContent", [{"uri": uri}])
    if _is_success(resp):
        print(f"📺 Input → {uri}")
    elif resp is None:
        print("⚠️  No answer.")
        sys.exit(1)


def cmd_get_input(_args):
    resp = sony_call("avContent", "getPlayingContentInfo", [{}])
    result = _get_result(resp)
    if result is None:
        print("📴 No answer or error.")
        return
    uri   = result.get("uri", "unknown")
    title = result.get("title", "")
    print(f"📺 Current input: {uri}  {('('+title+')') if title else ''}")


def cmd_volume(args):
    val = max(0, min(100, int(args.value)))
    resp = sony_call("audio", "setAudioVolume",
                     [{"target": "speaker", "volume": str(val)}])
    if _is_success(resp):
        print(f"🔊 Volume → {val}")
    else:
        print(f"⚠️  Volume response: {resp}")


def cmd_get_volume(_args):
    resp = sony_call("audio", "getVolumeInformation", [{}])
    result = _get_result(resp)
    if result is None:
        print("📴 No answer.")
        return
    # result is a list of audio targets
    if isinstance(result, list):
        for item in result:
            target = item.get("target", "?")
            vol    = item.get("volume", "?")
            muted  = item.get("mute", False)
            print(f"🔊 {target}: volume={vol}  mute={'on' if muted else 'off'}")
    else:
        print(f"🔊 Volume info: {result}")


def cmd_mute(args):
    state = args.state == "on"
    resp = sony_call("audio", "setAudioMute", [{"status": state}])
    if _is_success(resp):
        print(f"🔇 Mute {args.state}")
    else:
        print(f"⚠️  Mute response: {resp}")


def cmd_picture_mute(args):
    if args.state == "toggle":
        # No direct toggle in REST API — read current state and flip
        resp = sony_call("video", "getPictureMuteStatus", [{}])
        result = _get_result(resp)
        current = result.get("status", False) if result else False
        args.state = "off" if current else "on"
        print(f"   (toggling to {args.state})")

    state = args.state == "on"
    resp = sony_call("video", "setPictureMuteStatus", [{"status": state}])
    if _is_success(resp):
        print(f"🖥  Picture mute {args.state}")
    else:
        # Fallback: some models use the IRCC picture_off key
        print(f"⚠️  picture-mute not supported via REST on this model; trying IRCC key...")
        key_args = argparse.Namespace(key="picture_off" if state else "picture_off")
        cmd_key(key_args)


def cmd_sysinfo(_args):
    resp = sony_call("system", "getSystemInformation")
    result = _get_result(resp)
    if result is None:
        print("📴 No answer.")
        return
    for k, v in result.items():
        if v:
            print(f"  {k}: {v}")


def cmd_raw(args):
    """Send a raw REST API call: SERVICE METHOD [JSON_PARAMS]"""
    import json as _json
    params = []
    if args.params:
        try:
            params = _json.loads(args.params)
        except _json.JSONDecodeError as e:
            print(f"❌ Invalid JSON params: {e}")
            sys.exit(1)
    resp = sony_call(args.service, args.method, params)
    import json as _json
    print(_json.dumps(resp, indent=2))


# ─── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bravia",
        description="Sony Bravia REST API Remote (consumer / Google TV models)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bravia.py on
  python bravia.py set-input hdmi2
  python bravia.py volume 30
  python bravia.py key home
  python bravia.py raw avContent getContentList '[{"source":"extInput:hdmi"}]'
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("on",           help="Wake TV (WoL + power on)").set_defaults(func=cmd_on)
    sub.add_parser("off",          help="Power off TV").set_defaults(func=cmd_off)
    sub.add_parser("power-state",  help="Get power state").set_defaults(func=cmd_power_state)
    sub.add_parser("status",       help="Reachability + power state").set_defaults(func=cmd_status)
    sub.add_parser("sysinfo",      help="Get system information").set_defaults(func=cmd_sysinfo)

    k = sub.add_parser("key", help="Press a remote key (IRCC)")
    k.add_argument("key", help="Key name (run 'keys' to list)")
    k.set_defaults(func=cmd_key)

    sub.add_parser("keys", help="List remote keys").set_defaults(func=cmd_keys)

    si = sub.add_parser("set-input", help="Switch input")
    si.add_argument("input_uri", help="hdmi1 / hdmi2 / hdmi3 / hdmi4 / component1 / composite1")
    si.set_defaults(func=cmd_set_input)

    sub.add_parser("get-input",    help="Get current input").set_defaults(func=cmd_get_input)

    v = sub.add_parser("volume", help="Set volume (0-100)")
    v.add_argument("value", help="Integer 0-100")
    v.set_defaults(func=cmd_volume)

    sub.add_parser("get-volume",   help="Get current volume").set_defaults(func=cmd_get_volume)

    m = sub.add_parser("mute", help="Mute on/off")
    m.add_argument("state", choices=["on", "off"])
    m.set_defaults(func=cmd_mute)

    pm = sub.add_parser("picture-mute", help="Picture mute on/off/toggle (screen black)")
    pm.add_argument("state", choices=["on", "off", "toggle"])
    pm.set_defaults(func=cmd_picture_mute)

    r = sub.add_parser("raw", help="Send a raw REST API call")
    r.add_argument("service", help="API service (e.g. system, audio, avContent, ircc)")
    r.add_argument("method",  help="Method name (e.g. getPowerStatus)")
    r.add_argument("params",  nargs="?", default=None,
                   help="JSON params array (optional, e.g. '[{\"target\":\"speaker\"}]')")
    r.set_defaults(func=cmd_raw)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()