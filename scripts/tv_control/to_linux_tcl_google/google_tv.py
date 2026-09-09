#!/usr/bin/env python3
"""
Google TV / Android TV Remote Control (ADB)
============================================
Controls TCL, Hisense, and other Google TV / Android TV displays over ADB.
TCP port 5555, no authentication required once pairing is accepted on the TV.

Tested on: TCL and Hisense Google TV models.
(For Sony Bravia, use bravia.py instead.)

Setup on TV:
  Settings -> Device Preferences -> About -> Build number (tap 7x) ->
            Developer options -> USB debugging: ON
            (some models: Network debugging: ON)

Then on first connect, accept the RSA key prompt on the TV screen.

Requires: adb-shell  (pip install adb-shell)

Usage:
    python google_tv.py <command> [args]
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
import os

try:
    from adb_shell.adb_device import AdbDeviceTcp
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner
    from adb_shell.auth.keygen import keygen
except ImportError:
    print("Missing dependency: pip install adb-shell")
    sys.exit(1)

# ---- Configuration ---------------------------------------------------------
TV_IP           = "192.168.14.136"
TV_PORT         = 5555
TV_MAC          = "48:87:b8:ab:34:37"
TV_BROADCAST    = "192.168.14.255"
ADB_KEY_PATH    = os.path.expanduser("~/.android/adbkey")  # <-- add this back
REQUEST_TIMEOUT = 10

# ---- Android Keycodes ------------------------------------------------------

KEYCODES = {
    "power":            "KEYCODE_POWER",
    "tv_power":         "KEYCODE_POWER",
    "up":               "KEYCODE_DPAD_UP",
    "down":             "KEYCODE_DPAD_DOWN",
    "left":             "KEYCODE_DPAD_LEFT",
    "right":            "KEYCODE_DPAD_RIGHT",
    "confirm":          "KEYCODE_DPAD_CENTER",
    "ok":               "KEYCODE_DPAD_CENTER",
    "home":             "KEYCODE_HOME",
    "back":             "KEYCODE_BACK",
    "return":           "KEYCODE_BACK",
    "menu":             "KEYCODE_MENU",
    "options":          "KEYCODE_MENU",
    "settings":         "KEYCODE_SETTINGS",
    "display":          "KEYCODE_INFO",
    "info":             "KEYCODE_INFO",
    "num0":             "KEYCODE_0",
    "num1":             "KEYCODE_1",
    "num2":             "KEYCODE_2",
    "num3":             "KEYCODE_3",
    "num4":             "KEYCODE_4",
    "num5":             "KEYCODE_5",
    "num6":             "KEYCODE_6",
    "num7":             "KEYCODE_7",
    "num8":             "KEYCODE_8",
    "num9":             "KEYCODE_9",
    "dot":              "KEYCODE_PERIOD",
    "vol_up":           "KEYCODE_VOLUME_UP",
    "vol_down":         "KEYCODE_VOLUME_DOWN",
    "mute":             "KEYCODE_VOLUME_MUTE",
    "ch_up":            "KEYCODE_CHANNEL_UP",
    "ch_down":          "KEYCODE_CHANNEL_DOWN",
    "red":              "KEYCODE_PROG_RED",
    "green":            "KEYCODE_PROG_GREEN",
    "yellow":           "KEYCODE_PROG_YELLOW",
    "blue":             "KEYCODE_PROG_BLUE",
    "play":             "KEYCODE_MEDIA_PLAY",
    "pause":            "KEYCODE_MEDIA_PAUSE",
    "play_pause":       "KEYCODE_MEDIA_PLAY_PAUSE",
    "stop":             "KEYCODE_MEDIA_STOP",
    "ff":               "KEYCODE_MEDIA_FAST_FORWARD",
    "forward":          "KEYCODE_MEDIA_FAST_FORWARD",
    "rewind":           "KEYCODE_MEDIA_REWIND",
    "next":             "KEYCODE_MEDIA_NEXT",
    "prev":             "KEYCODE_MEDIA_PREVIOUS",
    "input":            "KEYCODE_TV_INPUT",
    "hdmi1":            "KEYCODE_TV_INPUT_HDMI_1",
    "hdmi2":            "KEYCODE_TV_INPUT_HDMI_2",
    "hdmi3":            "KEYCODE_TV_INPUT_HDMI_3",
    "hdmi4":            "KEYCODE_TV_INPUT_HDMI_4",
    "sleep":            "KEYCODE_SLEEP",
    "wake":             "KEYCODE_WAKEUP",
    "subtitle":         "KEYCODE_CAPTIONS",
    "search":           "KEYCODE_SEARCH",
    "microphone":       "KEYCODE_VOICE_ASSIST",
    "picture_off":      "KEYCODE_SLEEP",
    "action_menu":      "KEYCODE_MENU",
    "sync_menu":        "KEYCODE_MENU",
    "wide":             "KEYCODE_ZOOM_IN",
    "help":             "KEYCODE_HELP",
}

APP_PACKAGES = {
    "netflix":  "com.netflix.ninja",
    "youtube":  "com.google.android.youtube.tv",
    "tubi":     "com.tubitv",
    "fast":     "com.wbd.stream",
    "prime":    "com.amazon.amazonvideo.livingroom",
    "disney":   "com.disney.disneyplus",
    "hulu":     "com.hulu.plus",
}

# ---- ADB Key Management ----------------------------------------------------

def _ensure_adb_keys():
    os.makedirs(os.path.dirname(ADB_KEY_PATH), exist_ok=True)
    if not os.path.exists(ADB_KEY_PATH):
        print(f"Generating ADB keys at {ADB_KEY_PATH}...")
        keygen(ADB_KEY_PATH)
        print("ADB keys generated.")


def _load_signer() -> PythonRSASigner:
    _ensure_adb_keys()
    with open(ADB_KEY_PATH, "rb") as f:
        priv = f.read()
    with open(ADB_KEY_PATH + ".pub", "rb") as f:
        pub = f.read()
    return PythonRSASigner(pub, priv)


# ---- ADB Transport ---------------------------------------------------------

def _connect() -> AdbDeviceTcp:
    signer = _load_signer()
    device = AdbDeviceTcp(TV_IP, TV_PORT, default_transport_timeout_s=REQUEST_TIMEOUT)
    device.connect(rsa_keys=[signer], transport_timeout_s=REQUEST_TIMEOUT, auth_timeout_s=REQUEST_TIMEOUT)
    return device


def adb_shell(command: str) -> str | None:
    try:
        device = _connect()
        result = device.shell(command)
        device.close()
        return result.strip() if result else ""
    except Exception as e:
        print(f"ADB error: {e}")
        return None


def adb_keyevent(keycode: str) -> bool:
    result = adb_shell(f"input keyevent {keycode}")
    return result is not None


# ---- Connectivity ----------------------------------------------------------

def is_tv_reachable() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        return s.connect_ex((TV_IP, TV_PORT)) == 0
    except Exception:
        return False
    finally:
        s.close()


# ---- Power State -----------------------------------------------------------

def get_power_state() -> str | None:
    """Return 'active', 'standby', or None if unreachable."""
    result = adb_shell("dumpsys power | grep 'Display Power'")
    if result is None:
        return None
    if "ON" in result.upper():
        return "active"
    return "standby"

def send_wol(mac: str, broadcast: str):
    """Send Wake-on-LAN magic packet."""
    mac_bytes = bytes.fromhex(mac.replace(":", ""))
    magic = b'\xff' * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(magic, (broadcast, 9))
    print(f"WOL magic packet sent to {mac}")

# ---- Commands --------------------------------------------------------------

def cmd_on(_args):
    state = get_power_state()
    if state == "active":
        print("TV is already ON - skipping.")
        return
    if not is_tv_reachable():
        print("TV not reachable - sending WOL packet...")
        send_wol(TV_MAC, TV_BROADCAST)
        print("Waiting for TV to boot...")
        time.sleep(15)
        if not is_tv_reachable():
            print("TV still not reachable after WOL.")
            sys.exit(1)
    print(f"TV state is '{state}' - waking with KEYCODE_POWER...")
    if adb_keyevent("KEYCODE_POWER"):
        print("Wake sent.")
    else:
        print("Wake failed.")
        sys.exit(1)


def cmd_off(_args):
    state = get_power_state()
    if state != "active":
        print(f"TV is already OFF (state='{state}') - skipping.")
        return
    print("TV is ON - sleeping...")
    if adb_keyevent("KEYCODE_SLEEP"):
        print("Sleep sent.")
    else:
        print("Sleep failed.")
        sys.exit(1)


def cmd_power_state(_args):
    state = get_power_state()
    if state is None:
        print("No answer (TV likely off or ADB not reachable).")
        return
    icon = "Power ON" if state == "active" else "Power STANDBY/OFF"
    print(f"{icon} (state={state})")


def cmd_status(_args):
    print(f"Checking {TV_IP}:{TV_PORT}...")
    if is_tv_reachable():
        print("ADB server is reachable.")
        cmd_power_state(_args)
    else:
        print("TV ADB port not reachable.")
        print("Check: Developer Options -> USB/Network Debugging is ON.")


def cmd_key(args):
    name = args.key.lower().replace("-", "_")
    keycode = KEYCODES.get(name)
    if keycode is None:
        print(f"Unknown key '{args.key}' - run 'keys' to see available keys.")
        sys.exit(1)
    if adb_keyevent(keycode):
        print(f"Key: {name} ({keycode})")
    else:
        print(f"Key '{name}' failed.")
        sys.exit(1)


def cmd_keys(_args):
    print("Available remote keys (case-insensitive, '-' or '_' interchangeable):")
    for name in sorted(KEYCODES.keys()):
        print(f"  {name:<20} -> {KEYCODES[name]}")


def cmd_set_input(args):
    spec = args.input_uri.lower().strip()
    keycode = KEYCODES.get(spec)
    if keycode and keycode.startswith("KEYCODE_TV_INPUT"):
        if adb_keyevent(keycode):
            print(f"Input -> {spec}")
        else:
            print(f"Input switch failed.")
            sys.exit(1)
    else:
        print(f"No direct keycode for '{spec}' - opening input picker...")
        adb_keyevent("KEYCODE_TV_INPUT")


def cmd_get_input(_args):
    result = adb_shell("dumpsys activity activities | grep 'mCurrentFocus'")
    if result is None:
        print("No answer.")
        return
    print(f"Current focus: {result}")


def cmd_volume(args):
    val = max(0, min(100, int(args.value)))
    max_vol = adb_shell("media volume --stream 3 --get | grep -oP 'max=\\K[0-9]+'")
    try:
        max_steps = int(max_vol.strip()) if max_vol else 15
    except ValueError:
        max_steps = 15
    steps = round(val / 100 * max_steps)
    result = adb_shell(f"media volume --stream 3 --set {steps}")
    if result is not None:
        print(f"Volume -> {val}% ({steps}/{max_steps} steps)")
    else:
        print("Volume set failed.")


def cmd_mute(args):
    if args.state == "on":
        result = adb_shell("media volume --stream 3 --mute")
    else:
        result = adb_shell("media volume --stream 3 --unmute")
    if result is not None:
        print(f"Mute {args.state}")
    else:
        print("Mute failed.")


def cmd_launch_app(args):
    name = args.app.lower()
    package = APP_PACKAGES.get(name, args.app)
    result = adb_shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
    if result is not None and "Events injected: 1" in result:
        print(f"Launched: {package}")
    else:
        print(f"Launch may have failed: {result}")


def cmd_apps(_args):
    print("Known app shortcuts:")
    for name, pkg in APP_PACKAGES.items():
        print(f"  {name:<12} -> {pkg}")
    print("\nYou can also pass a raw package name to 'launch-app'.")


def cmd_raw(args):
    result = adb_shell(args.shell_command)
    if result is not None:
        print(result)
    else:
        print("Command failed or no output.")


def cmd_pair(_args):
    print(f"Attempting ADB connection to {TV_IP}:{TV_PORT}...")
    print("Make sure to accept the RSA key prompt on the TV screen.")
    try:
        device = _connect()
        result = device.shell("getprop ro.product.model")
        device.close()
        print(f"Connected! TV model: {result.strip()}")
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Check: Developer Options -> USB/Network Debugging is ON.")
        sys.exit(1)


# ---- CLI -------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="google_tv",
        description="Google TV / Android TV Remote (TCL, Hisense) via ADB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python google_tv.py pair
  python google_tv.py on
  python google_tv.py key home
  python google_tv.py set-input hdmi1
  python google_tv.py launch-app netflix
  python google_tv.py volume 30
  python google_tv.py raw "getprop ro.product.model"
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("pair",        help="Test ADB connection (run this first)").set_defaults(func=cmd_pair)
    sub.add_parser("on",          help="Wake TV").set_defaults(func=cmd_on)
    sub.add_parser("off",         help="Sleep TV").set_defaults(func=cmd_off)
    sub.add_parser("power-state", help="Get power state").set_defaults(func=cmd_power_state)
    sub.add_parser("status",      help="Reachability + power state").set_defaults(func=cmd_status)

    k = sub.add_parser("key", help="Press a remote key")
    k.add_argument("key", help="Key name (run 'keys' to list)")
    k.set_defaults(func=cmd_key)

    sub.add_parser("keys",        help="List remote keys").set_defaults(func=cmd_keys)

    si = sub.add_parser("set-input", help="Switch input")
    si.add_argument("input_uri",  help="hdmi1 / hdmi2 / hdmi3 / hdmi4")
    si.set_defaults(func=cmd_set_input)

    sub.add_parser("get-input",   help="Get current input/focus").set_defaults(func=cmd_get_input)

    v = sub.add_parser("volume",  help="Set volume (0-100)")
    v.add_argument("value",       help="Integer 0-100")
    v.set_defaults(func=cmd_volume)

    m = sub.add_parser("mute",    help="Mute on/off")
    m.add_argument("state",       choices=["on", "off"])
    m.set_defaults(func=cmd_mute)

    la = sub.add_parser("launch-app", help="Launch an app by name or package")
    la.add_argument("app",        help="App name (run 'apps' to list) or package name")
    la.set_defaults(func=cmd_launch_app)

    sub.add_parser("apps",        help="List known app shortcuts").set_defaults(func=cmd_apps)

    r = sub.add_parser("raw",     help="Run a raw ADB shell command")
    r.add_argument("shell_command", help="Shell command (e.g. 'getprop ro.product.model')")
    r.set_defaults(func=cmd_raw)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
