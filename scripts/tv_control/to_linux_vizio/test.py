#!/usr/bin/env python3
"""
Vizio SmartCast TV Remote Control
====================================
Control your Vizio SmartCast TV from the command line.
Based on: https://github.com/exiva/Vizio_SmartCast_API

Zero external dependencies — uses only Python stdlib.

Usage:
    python vizio_tv.py <command> [args]

First-time setup:
    1. Find your TV's IP (check router or run: python vizio_tv.py discover)
    2. Edit TV_IP below (and TV_PORT if needed)
    3. Run: python vizio_tv.py pair
    4. Enter the PIN shown on your TV screen
    5. Auth token is saved automatically
"""

from __future__ import annotations

import argparse
import json
import os
import readline  # enables input() line editing
import socket
import ssl
import struct
import sys
import time
import urllib.request
import urllib.error

# ─── Configuration ──────────────────────────────────────────────────────────
# Update these for your TV

# TV_IP = "10.19.37.243"     # e.g. "192.168.10.50"
TV_IP = "192.168.14.120"
TV_PORT = 7345                    # 7345 for firmware 4.0+, 9000 for older
TV_MAC = "14:C6:7D:15:31:56"     # For Wake-on-LAN (find in TV settings)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(SCRIPT_DIR, "vizio_auth.json")
DEVICE_NAME = "Python Vizio Remote"
DEVICE_ID = "python-vizio-remote-001"

# ─── Remote Key Codes (Codeset, Code) ───────────────────────────────────────

KEYS = {
    # Power (codeset 11)
    "power_off":     (11, 0),
    "power_on":      (11, 1),
    "power_toggle":  (11, 2),

    # Volume (codeset 5)
    "vol_down":      (5, 0),
    "vol_up":        (5, 1),
    "mute_off":      (5, 2),
    "mute_on":       (5, 3),
    "mute_toggle":   (5, 4),

    # Input (codeset 7)
    "input_cycle":   (7, 1),

    # Channel (codeset 8)
    "ch_down":       (8, 0),
    "ch_up":         (8, 1),
    "ch_prev":       (8, 2),

    # Video / Picture (codeset 6)
    "pic_mode":      (6, 0),
    "wide_mode":     (6, 1),
    "wide_cycle":    (6, 2),

    # Color buttons (codeset 9)
    "red":           (9, 0),
    "green":         (9, 1),
    "yellow":        (9, 2),
    "blue":          (9, 3),

    # D-Pad (codeset 3)
    "up":            (3, 8),
    "down":          (3, 0),
    "left":          (3, 1),
    "right":         (3, 7),
    "ok":            (3, 2),
    "back":          (3, 4),
    "exit":          (3, 5),

    # Nav (codeset 4)
    "menu":          (4, 8),
    "home":          (4, 3),
    "info":          (4, 6),
    "smartcast":     (4, 3),
    "guide":         (4, 0),
    "dvr":           (4, 5),

    # Transport (codeset 2)
    "play":          (2, 3),
    "pause":         (2, 2),
    "stop":          (2, 0),
    "ff":            (2, 1),
    "rewind":        (2, 4),

    # CC (codeset 13)
    "cc_toggle":     (13, 4),
    "cc_on":         (13, 1),
    "cc_off":        (13, 0),

    # Launch (codeset 10)
    "launch_smartcast": (10, 0),
}

# Well-known app IDs
APPS = {
    "netflix":    {"NAME_SPACE": 3, "APP_ID": "1",  "MESSAGE": None},
    "hulu":       {"NAME_SPACE": 2, "APP_ID": "3",  "MESSAGE": None},
    "prime":      {"NAME_SPACE": 2, "APP_ID": "4",  "MESSAGE": None},
    "plex":       {"NAME_SPACE": 2, "APP_ID": "9",  "MESSAGE": None},
    "youtube_tv": {"NAME_SPACE": 5, "APP_ID": "1",  "MESSAGE": None},
    "nbc":        {"NAME_SPACE": 2, "APP_ID": "10", "MESSAGE": None},
    "vudu":       {"NAME_SPACE": 2, "APP_ID": "21",
                   "MESSAGE": "https://my.vudu.com/castReceiver/index.html?launch-source=app-icon"},
    "watchfree":  {"NAME_SPACE": 2, "APP_ID": "22", "MESSAGE": None},
    "cbs":        {"NAME_SPACE": 2, "APP_ID": "37", "MESSAGE": None},
    "redbox":     {"NAME_SPACE": 2, "APP_ID": "41", "MESSAGE": None},
    "pluto": {
        "NAME_SPACE": 0, "APP_ID": "E6F74C01",
        "MESSAGE": json.dumps({
            "CAST_NAMESPACE": "urn:x-cast:tv.pluto",
            "CAST_MESSAGE": {"command": "initializePlayback", "channel": "", "episode": "", "time": 0}
        })
    },
    "xumo": {
        "NAME_SPACE": 0, "APP_ID": "36E1EA1F",
        "MESSAGE": json.dumps({
            "CAST_NAMESPACE": "urn:x-cast:com.google.cast.media",
            "CAST_MESSAGE": {"type": "LOAD", "media": {}, "autoplay": True, "currentTime": 0, "customData": {}}
        })
    },
}


# ─── Auth Token Persistence ─────────────────────────────────────────────────

def load_auth() -> str | None:
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE) as f:
            data = json.load(f)
            return data.get("auth_token")
    return None


def save_auth(token: str, pairing_token: int = 0):
    with open(AUTH_FILE, "w") as f:
        json.dump({
            "auth_token": token,
            "pairing_req_token": pairing_token,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "tv_ip": TV_IP,
            "tv_port": TV_PORT,
        }, f, indent=2)
    print(f"💾 Auth saved to {AUTH_FILE}")


def require_auth() -> str:
    token = load_auth()
    if not token:
        print("❌ Not paired. Run: python vizio_tv.py pair")
        sys.exit(1)
    return token


# ─── HTTP Client (SSL verification disabled for self-signed cert) ────────────

def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _api_url(path: str) -> str:
    return f"https://{TV_IP}:{TV_PORT}{path}"


def api_get(path: str, auth: str | None = None) -> dict:
    url = _api_url(path)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("AUTH", auth)

    try:
        with urllib.request.urlopen(req, context=_make_ssl_context(), timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": str(e), "body": body}
    except Exception as e:
        return {"error": str(e)}


def api_put(path: str, body: dict, auth: str | None = None) -> dict:
    url = _api_url(path)
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("AUTH", auth)

    try:
        with urllib.request.urlopen(req, context=_make_ssl_context(), timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return json.loads(body)
        except Exception:
            return {"error": str(e), "body": body}
    except Exception as e:
        return {"error": str(e)}


# ─── Wake-on-LAN ────────────────────────────────────────────────────────────

def send_wol(mac: str, broadcast: str = "255.255.255.255", port: int = 9):
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(magic, (broadcast, port))


# ─── SSDP Discovery ─────────────────────────────────────────────────────────

def ssdp_discover(timeout: int = 5) -> list[dict]:
    """Discover Vizio SmartCast devices on the local network."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        "ST: urn:schemas-kinoma-com:device:shell:1\r\n"
        "\r\n"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(msg.encode(), ("239.255.255.250", 1900))

    devices = []
    end = time.time() + timeout
    while time.time() < end:
        try:
            data, addr = sock.recvfrom(4096)
            resp = data.decode(errors="replace")
            location = ""
            for line in resp.split("\r\n"):
                if line.lower().startswith("location:"):
                    location = line.split(":", 1)[1].strip()
            devices.append({"ip": addr[0], "port": addr[1], "location": location})
        except socket.timeout:
            break
    sock.close()
    return devices


# ═══════════════════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

# ─── Discovery & Pairing ────────────────────────────────────────────────────

def cmd_discover(_args):
    """Discover Vizio TVs on the network via SSDP."""
    print("🔍 Scanning for Vizio SmartCast devices (5s)...")
    devices = ssdp_discover()
    if not devices:
        print("   No devices found. Check that TV is on and on same network.")
    for d in devices:
        print(f"   📺 {d['ip']}:{d['port']}  {d['location']}")


def cmd_pair(_args):
    """Pair with the TV to get an auth token."""
    if TV_IP == "YOUR_VIZIO_TV_IP":
        print("❌ Edit TV_IP in the script first! (or run 'discover' to find it)")
        sys.exit(1)

    print(f"🔗 Starting pairing with {TV_IP}:{TV_PORT}...")

    # Step 1: Initiate pairing
    resp = api_put("/pairing/start", {
        "DEVICE_NAME": DEVICE_NAME,
        "DEVICE_ID": DEVICE_ID,
    })

    status = resp.get("STATUS", {}).get("RESULT", "")
    if status != "SUCCESS":
        print(f"❌ Pairing start failed: {resp}")
        sys.exit(1)

    item = resp.get("ITEM", {})
    pairing_token = item.get("PAIRING_REQ_TOKEN")
    challenge_type = item.get("CHALLENGE_TYPE", 1)
    print(f"   Pairing token: {pairing_token}")

    # Step 2: Get PIN from user
    print("\n📺 Look at your TV screen for a 4-digit PIN code.")
    pin = input("   Enter PIN: ").strip()

    # Step 3: Submit challenge
    resp = api_put("/pairing/pair", {
        "DEVICE_ID": DEVICE_ID,
        "CHALLENGE_TYPE": challenge_type,
        "RESPONSE_VALUE": pin,
        "PAIRING_REQ_TOKEN": pairing_token,
    })

    status = resp.get("STATUS", {}).get("RESULT", "")
    if status != "SUCCESS":
        detail = resp.get("STATUS", {}).get("DETAIL", "unknown")
        print(f"❌ Pairing failed: {detail}")
        sys.exit(1)

    auth_token = resp.get("ITEM", {}).get("AUTH_TOKEN", "")
    if auth_token:
        save_auth(auth_token, pairing_token)
        print(f"🎉 Paired! Auth token: {auth_token[:8]}...")
    else:
        print(f"⚠️  Unexpected response: {resp}")


def cmd_cancel_pair(_args):
    """Cancel an in-progress pairing."""
    resp = api_put("/pairing/cancel", {
        "DEVICE_ID": DEVICE_ID,
        "CHALLENGE_TYPE": 1,
        "RESPONSE_VALUE": "1111",
        "PAIRING_REQ_TOKEN": 0,
    })
    print(f"Pairing cancelled: {resp.get('STATUS', {}).get('RESULT', 'unknown')}")


# ─── Power ───────────────────────────────────────────────────────────────────

def cmd_on(_args):
    """Turn on TV via Wake-on-LAN."""
    if TV_MAC == "XX:XX:XX:XX:XX:XX":
        auth = load_auth()
        if auth:
            print("📡 Sending power on command...")
            _send_key("power_on", auth)
            print("   Also sending WoL (set TV_MAC in script for reliable WoL)...")
        else:
            print("⚠️  Set TV_MAC in the script for Wake-on-LAN, or pair first.")
            return
    else:
        print(f"📡 Sending Wake-on-LAN to {TV_MAC}...")
        for _ in range(4):
            send_wol(TV_MAC, broadcast="192.168.14.255")
            time.sleep(0.5)
        print("✅ WoL packets sent.")


def cmd_off(_args):
    auth = require_auth()
    _send_key("power_off", auth)
    print("📴 TV powering off.")


def cmd_power_toggle(_args):
    auth = require_auth()
    _send_key("power_toggle", auth)
    print("⚡ Power toggled.")


def cmd_power_state(_args):
    auth = require_auth()
    resp = api_get("/state/device/power_mode", auth)
    items = resp.get("ITEMS", [])
    if items:
        val = items[0].get("VALUE")
        state = "ON" if val == 1 else "STANDBY" if val == 0 else f"UNKNOWN ({val})"
        print(f"⚡ Power state: {state}")
    else:
        print(f"⚠️  {resp}")


# ─── Volume / Audio ──────────────────────────────────────────────────────────

def cmd_vol_up(_args):
    auth = require_auth()
    _send_key("vol_up", auth)
    print("🔊 Volume up")


def cmd_vol_down(_args):
    auth = require_auth()
    _send_key("vol_down", auth)
    print("🔉 Volume down")


def cmd_mute(args):
    auth = require_auth()
    if args.state == "on":
        _send_key("mute_on", auth)
    elif args.state == "off":
        _send_key("mute_off", auth)
    else:
        _send_key("mute_toggle", auth)
    print(f"🔇 Mute {args.state or 'toggled'}")


def cmd_get_audio(_args):
    auth = require_auth()
    resp = api_get("/menu_native/dynamic/tv_settings/audio", auth)
    _print_settings(resp)


# ─── Channel ─────────────────────────────────────────────────────────────────

def cmd_ch_up(_args):
    auth = require_auth()
    _send_key("ch_up", auth)
    print("📺 Channel up")


def cmd_ch_down(_args):
    auth = require_auth()
    _send_key("ch_down", auth)
    print("📺 Channel down")


def cmd_ch_prev(_args):
    auth = require_auth()
    _send_key("ch_prev", auth)
    print("📺 Previous channel")


# ─── Input Sources ───────────────────────────────────────────────────────────

def cmd_input_cycle(_args):
    auth = require_auth()
    _send_key("input_cycle", auth)
    print("🔄 Input cycled")


def cmd_current_input(_args):
    auth = require_auth()
    resp = api_get("/menu_native/dynamic/tv_settings/devices/current_input", auth)
    items = resp.get("ITEMS", [])
    if items:
        print(f"📺 Current input: {items[0].get('VALUE', '?')} ({items[0].get('NAME', '?')})")
    else:
        print(f"⚠️  {resp}")


def cmd_inputs(_args):
    auth = require_auth()
    resp = api_get("/menu_native/dynamic/tv_settings/devices/name_input", auth)
    items = resp.get("ITEMS", [])
    if items:
        print(f"\n{'Name':<20} {'Label'}")
        print("─" * 40)
        for item in items:
            name = item.get("NAME", "?")
            val = item.get("VALUE", {})
            label = val.get("NAME", "?") if isinstance(val, dict) else val
            print(f"{name:<20} {label}")
    else:
        print(f"⚠️  {resp}")


def cmd_set_input(args):
    auth = require_auth()
    # First get current hashval
    resp = api_get("/menu_native/dynamic/tv_settings/devices/current_input", auth)
    items = resp.get("ITEMS", [])
    hashval = items[0].get("HASHVAL", 0) if items else 0

    resp = api_put("/menu_native/dynamic/tv_settings/devices/current_input", {
        "REQUEST": "MODIFY",
        "VALUE": args.input_name,
        "HASHVAL": hashval,
    }, auth)

    status = resp.get("STATUS", {}).get("RESULT", "")
    if status == "SUCCESS":
        print(f"📺 Input → {args.input_name}")
    else:
        print(f"⚠️  {resp.get('STATUS', resp)}")


# ─── Media Controls ──────────────────────────────────────────────────────────

def cmd_play(_args):
    auth = require_auth(); _send_key("play", auth); print("▶️  Play")

def cmd_pause(_args):
    auth = require_auth(); _send_key("pause", auth); print("⏸  Pause")

def cmd_stop(_args):
    auth = require_auth(); _send_key("stop", auth); print("⏹  Stop")

def cmd_ff(_args):
    auth = require_auth(); _send_key("ff", auth); print("⏩ Fast forward")

def cmd_rewind(_args):
    auth = require_auth(); _send_key("rewind", auth); print("⏪ Rewind")


# ─── Navigation / Remote Keys ───────────────────────────────────────────────

def cmd_key(args):
    key_name = args.key.lower()
    if key_name not in KEYS:
        print(f"❌ Unknown key '{args.key}'")
        print(f"   Run 'keys' to see available keys.")
        sys.exit(1)
    auth = require_auth()
    action = args.action.upper() if hasattr(args, "action") and args.action else "KEYPRESS"
    _send_key(key_name, auth, action=action)
    print(f"🎮 Key: {key_name} ({action})")


def cmd_keys(_args):
    print("Available remote keys:")
    categories = {}
    for name, (codeset, code) in sorted(KEYS.items()):
        cat = {
            0: "ASCII", 2: "Transport", 3: "D-Pad", 4: "Nav",
            5: "Audio", 6: "Video", 7: "Input", 8: "Channel",
            9: "Color", 10: "Launch", 11: "Power", 13: "CC",
        }.get(codeset, f"Codeset {codeset}")
        categories.setdefault(cat, []).append((name, codeset, code))

    for cat, keys in sorted(categories.items()):
        print(f"\n  [{cat}]")
        for name, cs, code in keys:
            print(f"    {name:<20} codeset={cs} code={code}")


# ─── Apps ────────────────────────────────────────────────────────────────────

def cmd_launch(args):
    auth = require_auth()
    app_name = args.app_name.lower()

    if app_name in APPS:
        app = APPS[app_name]
        body = {
            "VALUE": {
                "NAME_SPACE": app["NAME_SPACE"],
                "APP_ID": app["APP_ID"],
            }
        }
        if app["MESSAGE"]:
            body["VALUE"]["MESSAGE"] = app["MESSAGE"]
    else:
        # Try as raw: namespace:app_id
        if ":" in app_name:
            ns, aid = app_name.split(":", 1)
            body = {"VALUE": {"NAME_SPACE": int(ns), "APP_ID": aid}}
        else:
            print(f"❌ Unknown app '{args.app_name}'")
            print(f"   Known apps: {', '.join(sorted(APPS.keys()))}")
            print(f"   Or use format: namespace:app_id (e.g. 2:3 for Hulu)")
            sys.exit(1)

    resp = api_put("/app/launch", body, auth)
    status = resp.get("STATUS", {}).get("RESULT", "")
    if status == "SUCCESS":
        print(f"🚀 Launched: {args.app_name}")
    else:
        print(f"⚠️  {resp.get('STATUS', resp)}")


def cmd_app_list(_args):
    print("Known SmartCast apps:")
    print(f"\n{'Name':<15} {'Namespace':<12} {'App ID'}")
    print("─" * 40)
    for name, info in sorted(APPS.items()):
        print(f"{name:<15} {info['NAME_SPACE']:<12} {info['APP_ID']}")


# ─── Settings ────────────────────────────────────────────────────────────────

def cmd_settings(args):
    auth = require_auth()
    path = f"/menu_native/dynamic/tv_settings/{args.category}"
    resp = api_get(path, auth)
    _print_settings(resp)


def cmd_set_setting(args):
    auth = require_auth()
    # Get current hashval
    cat_path = f"/menu_native/dynamic/tv_settings/{args.category}"
    resp = api_get(cat_path, auth)
    items = resp.get("ITEMS", [])

    target = None
    for item in items:
        if item.get("CNAME", "").lower() == args.setting.lower():
            target = item
            break

    if not target:
        print(f"❌ Setting '{args.setting}' not found in '{args.category}'")
        print(f"   Available: {[i.get('CNAME') for i in items]}")
        sys.exit(1)

    hashval = target.get("HASHVAL", 0)

    # Determine value type
    value = args.value
    try:
        value = int(value)
    except ValueError:
        pass

    resp = api_put(f"{cat_path}/{args.setting}", {
        "REQUEST": "MODIFY",
        "HASHVAL": hashval,
        "VALUE": value,
    }, auth)

    status = resp.get("STATUS", {}).get("RESULT", "")
    if status == "SUCCESS":
        print(f"✅ {args.category}/{args.setting} → {value}")
    else:
        print(f"⚠️  {resp.get('STATUS', resp)}")


# ─── System Info ─────────────────────────────────────────────────────────────

def cmd_sysinfo(_args):
    auth = require_auth()
    resp = api_get("/menu_native/dynamic/tv_settings/system/system_information/tv_information", auth)
    _print_settings(resp)


def cmd_network_info(_args):
    auth = require_auth()
    resp = api_get("/menu_native/dynamic/tv_settings/system/system_information/network_information", auth)
    _print_settings(resp)


# ─── Status ──────────────────────────────────────────────────────────────────

def cmd_status(_args):
    print(f"🔍 Checking {TV_IP}:{TV_PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        result = s.connect_ex((TV_IP, TV_PORT))
        if result == 0:
            print("✅ TV API server is reachable (TV is ON).")
            auth = load_auth()
            if auth:
                cmd_power_state(_args)
            else:
                print("   (not paired — run 'pair' for more details)")
        else:
            print("📴 TV appears to be OFF or unreachable.")
            print("   (The SmartCast API server shuts down in standby/eco mode)")
    finally:
        s.close()


# ─── Raw API ─────────────────────────────────────────────────────────────────

def cmd_raw_get(args):
    auth = load_auth()
    resp = api_get(args.path, auth)
    print(json.dumps(resp, indent=2, default=str))


def cmd_raw_put(args):
    auth = require_auth()
    body = json.loads(args.body)
    resp = api_put(args.path, body, auth)
    print(json.dumps(resp, indent=2, default=str))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _send_key(key_name: str, auth: str, action: str = "KEYPRESS"):
    codeset, code = KEYS[key_name]
    body = {
        "KEYLIST": [{
            "CODESET": codeset,
            "CODE": code,
            "ACTION": action,
        }]
    }
    resp = api_put("/key_command/", body, auth)
    status = resp.get("STATUS", {}).get("RESULT", "")
    if status != "SUCCESS":
        detail = resp.get("STATUS", {}).get("DETAIL", str(resp))
        if "requires_pairing" in detail.lower() or "requires_pairing" in status.lower():
            print("❌ Auth token expired. Run: python vizio_tv.py pair")
            sys.exit(1)
        print(f"⚠️  Key command response: {detail}")


def _print_settings(resp: dict):
    items = resp.get("ITEMS", [])
    if not items:
        print(f"⚠️  {resp}")
        return
    print()
    for item in items:
        name = item.get("NAME", "?")
        cname = item.get("CNAME", "")
        value = item.get("VALUE", "?")
        enabled = "✅" if item.get("ENABLED", True) else "  "
        itype = item.get("TYPE", "")

        if isinstance(value, dict):
            value = value.get("NAME", str(value))

        print(f"  {enabled} {name:<30} = {value}")
        if cname:
            print(f"       cname: {cname}  type: {itype}")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vizio_tv",
        description="Vizio SmartCast TV Remote Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔═══════════════════════════════════════════════════════════════╗
║  Quick reference:                                             ║
║    vizio_tv.py discover           Find TVs on network         ║
║    vizio_tv.py pair               Pair & get auth token       ║
║    vizio_tv.py on / off           Power on (WoL) / off        ║
║    vizio_tv.py vol-up / vol-down  Volume control              ║
║    vizio_tv.py key ok             Press OK / Enter             ║
║    vizio_tv.py launch netflix     Launch Netflix              ║
║    vizio_tv.py input HDMI-1       Switch to HDMI-1            ║
║    vizio_tv.py settings picture   View picture settings       ║
╚═══════════════════════════════════════════════════════════════╝
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── Discovery & Pairing ──
    sub.add_parser("discover", help="Find Vizio TVs on network (SSDP)").set_defaults(func=cmd_discover)
    sub.add_parser("pair", help="Pair with TV (get auth token)").set_defaults(func=cmd_pair)
    sub.add_parser("cancel-pair", help="Cancel in-progress pairing").set_defaults(func=cmd_cancel_pair)

    # ── Power ──
    sub.add_parser("on", help="Turn on TV (WoL / power-on key)").set_defaults(func=cmd_on)
    sub.add_parser("off", help="Turn off TV").set_defaults(func=cmd_off)
    sub.add_parser("power", help="Toggle power").set_defaults(func=cmd_power_toggle)
    sub.add_parser("power-state", help="Get power state").set_defaults(func=cmd_power_state)

    # ── Status / Info ──
    sub.add_parser("status", help="Check if TV is reachable").set_defaults(func=cmd_status)
    sub.add_parser("sysinfo", help="TV system information").set_defaults(func=cmd_sysinfo)
    sub.add_parser("netinfo", help="Network information").set_defaults(func=cmd_network_info)

    # ── Audio ──
    sub.add_parser("vol-up", help="Volume up").set_defaults(func=cmd_vol_up)
    sub.add_parser("vol-down", help="Volume down").set_defaults(func=cmd_vol_down)
    sub.add_parser("audio", help="Audio settings").set_defaults(func=cmd_get_audio)

    mute = sub.add_parser("mute", help="Mute (on/off/toggle)")
    mute.add_argument("state", nargs="?", choices=["on", "off"], default=None)
    mute.set_defaults(func=cmd_mute)

    # ── Channel ──
    sub.add_parser("ch-up", help="Channel up").set_defaults(func=cmd_ch_up)
    sub.add_parser("ch-down", help="Channel down").set_defaults(func=cmd_ch_down)
    sub.add_parser("ch-prev", help="Previous channel").set_defaults(func=cmd_ch_prev)

    # ── Input ──
    sub.add_parser("input-cycle", help="Cycle through inputs").set_defaults(func=cmd_input_cycle)
    sub.add_parser("input", help="Get current input").set_defaults(func=cmd_current_input)
    sub.add_parser("inputs", help="List all inputs").set_defaults(func=cmd_inputs)

    si = sub.add_parser("set-input", help="Switch to specific input")
    si.add_argument("input_name", help="e.g. HDMI-1, HDMI-2, COMP, TUNER")
    si.set_defaults(func=cmd_set_input)

    # ── Media ──
    sub.add_parser("play", help="Play").set_defaults(func=cmd_play)
    sub.add_parser("pause", help="Pause").set_defaults(func=cmd_pause)
    sub.add_parser("stop", help="Stop").set_defaults(func=cmd_stop)
    sub.add_parser("ff", help="Fast forward").set_defaults(func=cmd_ff)
    sub.add_parser("rewind", help="Rewind").set_defaults(func=cmd_rewind)

    # ── Apps ──
    sub.add_parser("apps", help="List known SmartCast apps").set_defaults(func=cmd_app_list)

    la = sub.add_parser("launch", help="Launch an app")
    la.add_argument("app_name", help="App name (run 'apps') or namespace:app_id")
    la.set_defaults(func=cmd_launch)

    # ── Remote key ──
    key = sub.add_parser("key", help="Send remote key press")
    key.add_argument("key", help="Key name (run 'keys' to list)")
    key.add_argument("--action", "-a", default="KEYPRESS",
                     choices=["KEYPRESS", "KEYDOWN", "KEYUP"])
    key.set_defaults(func=cmd_key)

    sub.add_parser("keys", help="List all remote keys").set_defaults(func=cmd_keys)

    # ── Settings ──
    st = sub.add_parser("settings", help="Read TV settings by category")
    st.add_argument("category", help="e.g. picture, audio, system, network, timers, cast")
    st.set_defaults(func=cmd_settings)

    ss = sub.add_parser("set", help="Write a TV setting")
    ss.add_argument("category", help="e.g. picture, audio")
    ss.add_argument("setting", help="Setting CNAME (from 'settings' output)")
    ss.add_argument("value", help="New value")
    ss.set_defaults(func=cmd_set_setting)

    # ── Raw API ──
    rg = sub.add_parser("get", help="Raw GET request")
    rg.add_argument("path", help="API path, e.g. /state/device/power_mode")
    rg.set_defaults(func=cmd_raw_get)

    rp = sub.add_parser("put", help="Raw PUT request")
    rp.add_argument("path", help="API path")
    rp.add_argument("body", help="JSON body")
    rp.set_defaults(func=cmd_raw_put)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
