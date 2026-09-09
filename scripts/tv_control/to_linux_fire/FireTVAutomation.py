#TODO: Fix Timings
#TODO: Fix IP address and MAC

#DONE (remember for other tvs):
#TODO: Check navigation sequences after UI updates
#TODO: Fix any problem with Youtube search
#TODO: Fix any problem with Tubi search
#TODO: App Exits
#TODO: Check if FAST is really FAST


import subprocess
import socket
import time
import logging
from datetime import datetime
import asyncio


# ==========================================
# Timing Constants (match firetv_experiment.sh)
# ==========================================
KEY_DELAY = 2           # Seconds between button presses
BOOT_DELAY = 25         # Initial wait after wake
MAX_BOOT_RETRIES = 5    # WoL/ADB retries if TV doesn't come up
BOOT_POLL_INTERVAL = 10 # Seconds between reachability checks
RUN_CMD_RETRIES = 3     # Retries per command on failure
RUN_CMD_RETRY_WAIT = 5  # Seconds between retries
WATCH_TIME = 900         # Seconds per scenario (SCENARIO_DURATION)
POWER_OFF_WAIT = 120     # Seconds after sleep before next wake
APP_LAUNCH_WAIT = 20    # Seconds to let an app fully load
NETFLIX_PREVIEW_WAIT = 300  # Seconds Netflix plays preview before navigating away


# ==========================================
# FireTV Configuration
# ==========================================
FIRETV_IP="192.168.14.135" # e.g. 192.168.10.60
FIRETV_PORT = 5555
FIRETV_MAC="28:73:F6:20:BA:95" # For Wake-on-LAN (find in Settings → My Fire TV → About → Network)


ADB_TARGET = f"{FIRETV_IP}:{FIRETV_PORT}"


# ==========================================
# App Package Names
# ==========================================
NETFLIX_PKG = "com.netflix.ninja"
YOUTUBE_PKG = "com.amazon.firetv.youtube"
TUBI_PKG = "com.tubitv"


# ==========================================
# Android Keycodes
# ==========================================
KEYCODE_HOME = 3
KEYCODE_BACK = 4
KEYCODE_UP = 19
KEYCODE_DOWN = 20
KEYCODE_LEFT = 21
KEYCODE_RIGHT = 22
KEYCODE_DPAD_CENTER = 23   # OK / Select
KEYCODE_ENTER = 66
KEYCODE_SLEEP = 223
KEYCODE_WAKEUP = 224


# ==========================================
# Logging
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"firetv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==========================================
# ADB Low-Level Helpers
# ==========================================

def _adb_cmd(*args):
    """Run an adb command targeting the FireTV, return (stdout, stderr, returncode)."""
    cmd = ["adb", "-s", ADB_TARGET] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _adb_shell(*args):
    """Run an adb shell command."""
    return _adb_cmd("shell", *args)


def _send_keyevent(keycode):
    """Send a single Android keyevent via ADB shell."""
    return _adb_shell("input", "keyevent", str(keycode))


def _has_adb_error(stdout, stderr):
    """Check if ADB output indicates a connection/network error."""
    combined = (stdout + " " + stderr).lower()
    error_keywords = [
        "error", "refused", "offline", "closed",
        "unable to connect", "no route", "timed out", "cannot connect"
    ]
    return any(kw in combined for kw in error_keywords)


def _send_wol(mac_address):
    """Send a Wake-on-LAN magic packet."""
    mac_bytes = bytes.fromhex(mac_address.replace(":", ""))
    magic = b'\xff' * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(magic, ('192.168.14.255', 9))
    logger.info(f"WoL sent to {mac_address}")


# ==========================================
# Robust Command Execution (mirrors run_cmd)
# ==========================================

async def run_cmd_key(keycode):
    """Send a keyevent with retry logic matching firetv_experiment.sh run_cmd."""
    for attempt in range(1, RUN_CMD_RETRIES + 1):
        stdout, stderr, rc = _send_keyevent(keycode)
        if _has_adb_error(stdout, stderr):
            logger.warning(f"Command failed (attempt {attempt}/{RUN_CMD_RETRIES}): keyevent {keycode}")
            if attempt < RUN_CMD_RETRIES:
                if not is_tv_reachable():
                    logger.warning("TV unreachable — attempting recovery...")
                    adb_reconnect()
                    if not is_tv_reachable():
                        if not await wait_for_tv():
                            return False
                else:
                    await asyncio.sleep(RUN_CMD_RETRY_WAIT)
        else:
            await asyncio.sleep(KEY_DELAY)
            return True
    logger.error(f"Command failed after {RUN_CMD_RETRIES} retries: keyevent {keycode}")
    await asyncio.sleep(KEY_DELAY)
    return False


async def run_cmd_launch(package):
    """Launch an app via monkey command with retry logic."""
    for attempt in range(1, RUN_CMD_RETRIES + 1):
        stdout, stderr, rc = _adb_shell(
            "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"
        )
        if _has_adb_error(stdout, stderr):
            logger.warning(f"Launch failed (attempt {attempt}/{RUN_CMD_RETRIES}): {package}")
            if attempt < RUN_CMD_RETRIES:
                if not is_tv_reachable():
                    adb_reconnect()
                    if not is_tv_reachable():
                        if not await wait_for_tv():
                            return False
                else:
                    await asyncio.sleep(RUN_CMD_RETRY_WAIT)
        else:
            await asyncio.sleep(KEY_DELAY)
            return True
    logger.error(f"Launch failed after {RUN_CMD_RETRIES} retries: {package}")
    await asyncio.sleep(KEY_DELAY)
    return False


# ==========================================
# Connectivity & Recovery
# ==========================================

def is_tv_reachable():
    """Check if FireTV is reachable via ADB (equivalent to tv_is_reachable)."""
    try:
        stdout, stderr, rc = _adb_cmd("get-state")
        return stdout.strip() == "device"
    except Exception:
        return False


def adb_reconnect():
    """Reconnect ADB to the FireTV."""
    logger.info("Reconnecting ADB...")
    try:
        subprocess.run(
            ["adb", "connect", ADB_TARGET],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass
    time.sleep(2)


async def connect():
    """Establish ADB connection (equivalent to Samsung's connect).
    Returns True on success, raises Exception on failure."""
    for attempt in range(1, MAX_BOOT_RETRIES + 1):
        try:
            logger.info(f"Connecting via ADB (attempt {attempt}/{MAX_BOOT_RETRIES})...")
            adb_reconnect()
            if is_tv_reachable():
                logger.info("Connected to FireTV.")
                return True
        except Exception as e:
            logger.warning(f"Connection attempt {attempt} failed: {e}")
        await asyncio.sleep(BOOT_POLL_INTERVAL)
    raise Exception("Could not connect after all retries.")


async def wait_for_tv():
    """Wait for FireTV to become reachable after power on.
    Mirrors firetv_experiment.sh wait_for_tv exactly."""
    logger.info("Waiting for Fire TV to become reachable...")
    await asyncio.sleep(BOOT_DELAY)

    adb_reconnect()

    attempt = 1
    while not is_tv_reachable():
        if attempt >= MAX_BOOT_RETRIES:
            logger.error(f"Fire TV unreachable after {MAX_BOOT_RETRIES} retries — last WoL + reconnect...")
            _send_wol(FIRETV_MAC)
            _send_keyevent(KEYCODE_WAKEUP)
            _send_keyevent(KEYCODE_HOME)
            await asyncio.sleep(BOOT_DELAY)
            adb_reconnect()
            if not is_tv_reachable():
                logger.error("FATAL: Fire TV not reachable. Skipping remaining commands.")
                return False
            return True
        logger.warning(f"Not reachable (attempt {attempt}/{MAX_BOOT_RETRIES}) — WoL + reconnect...")
        _send_wol(FIRETV_MAC)
        _send_keyevent(KEYCODE_WAKEUP)
        _send_keyevent(KEYCODE_HOME)
        await asyncio.sleep(BOOT_POLL_INTERVAL)
        adb_reconnect()
        attempt += 1

    logger.info("Fire TV is reachable.")
    return True


# ==========================================
# Power Control
# ==========================================

async def power_on():
    """Wake the FireTV (WoL + WAKEUP + HOME). Mirrors firetv.sh cmd_on."""
    logger.info("Waking Fire TV...")
    _send_wol(FIRETV_MAC)
    await asyncio.sleep(2)
    try:
        subprocess.run(["adb", "connect", ADB_TARGET], capture_output=True, text=True, timeout=10)
    except Exception:
        pass
    _send_keyevent(KEYCODE_WAKEUP)
    _send_keyevent(KEYCODE_HOME)
    logger.info("Wake sent.")
    if not await wait_for_tv():
        logger.warning("WARNING: Fire TV did not come up successfully.")


async def power_off():
    """Sleep the FireTV. Mirrors firetv.sh cmd_off."""
    logger.info("Sleeping Fire TV...")
    _send_keyevent(KEYCODE_SLEEP)
    await asyncio.sleep(POWER_OFF_WAIT)
    logger.info("Sleep sent.")


# ==========================================
# Navigation Helpers
# ==========================================

async def go_home():
    """Press HOME and wait. Mirrors firetv_experiment.sh go_home."""
    logger.info("Returning to Home screen...")
    # await run_cmd_key(KEYCODE_HOME)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await run_cmd_key(KEYCODE_BACK)
    await asyncio.sleep(2)


async def key_up():
    logger.info("Press Up key...")
    await run_cmd_key(KEYCODE_UP)


async def key_down():
    logger.info("Press Down key...")
    await run_cmd_key(KEYCODE_DOWN)


async def key_left():
    logger.info("Press Left key...")
    await run_cmd_key(KEYCODE_LEFT)


async def key_right():
    logger.info("Press Right key...")
    await run_cmd_key(KEYCODE_RIGHT)


async def key_ok():
    logger.info("Press OK key...")
    await run_cmd_key(KEYCODE_DPAD_CENTER)


async def key_back():
    logger.info("Press Back key...")
    await run_cmd_key(KEYCODE_BACK)


async def key_enter():
    logger.info("Press Enter key...")
    await run_cmd_key(KEYCODE_ENTER)


# ==========================================
# Base Position (firetv_experiment.sh)
#   up x8, down x1, back x1
# ==========================================

async def base_position():
    """Navigate to the known base position from Home screen.
    Mirrors firetv_experiment.sh base_position exactly."""
    logger.info("Navigating to base position...")
    for _ in range(8):
        await key_up()
    await key_down()
    await key_back()


# ==========================================
# Scenario Launchers
# Exact sequences from firetv_experiment.sh
# ==========================================

async def open_idle():
    logger.info("Launching IDLE...")
    await asyncio.sleep(850)

async def open_fast():
    """Launch FAST (Amazon Free Channels).
    base_position → right x6 → ok"""
    logger.info("Launching FAST...")
    await base_position()
    for _ in range(6):
        await key_right()
    await key_ok()
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)


async def open_netflix():
    """Launch Netflix via app launch.
    launch netflix → wait 30s → left → wait 360s → left x5"""
    logger.info("Launching Netflix...")
    await run_cmd_launch(NETFLIX_PKG)
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await asyncio.sleep(10)
    await key_left()
    #await asyncio.sleep(NETFLIX_PREVIEW_WAIT)
    for _ in range(5):
        logger.info("Watching Netflix")
        await asyncio.sleep(WATCH_TIME // 5)
        for _ in range(10):
            await key_left()
    


async def open_tubi():
    """Launch Tubi.
    base_position → right x5 → ok → ok → wait 20s → ok"""
    logger.info("Launching Tubi...")
    await base_position()
    for _ in range(5):
        await key_right()
    await key_ok()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await key_ok()
    logger.info("Watching Tubi")
    await asyncio.sleep(WATCH_TIME)


async def open_youtube():
    """Launch YouTube.
    base_position → right x4 → ok → ok → back → up →
    right x10 → left x8 → ok → right → ok →
    left → up → right → down x5 → ok"""
    logger.info("Launching YouTube...")
    await base_position()
    for _ in range(4):
        await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await key_back()
    await key_up()
    for _ in range(10):
        await key_right()
    for _ in range(8):
        await key_left()
    await key_ok()
    await asyncio.sleep(5)
    await key_right()
    await key_ok()
    logger.info("Watching YouTube")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna():
    """Launch Antenna (random channel).
    base_position → right → down → ok → ok"""
    logger.info("Launching Antenna (random)...")
    await base_position()
    await key_right()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_down()
    await key_down()
    await key_ok()
    logger.info("Watching Antenna")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_14_1():
    """Launch Antenna 14.1 (specific OTA sub-channel).
    base_position → right → down → ok → down → ok"""
    logger.info("Launching Antenna 14.1...")
    await base_position()
    await key_right()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_down()
    await key_down()
    await key_down()
    await key_ok()
    logger.info("Watching Antenna 14.1")
    await asyncio.sleep(WATCH_TIME)

async def open_antenna_10_1():
    """Launch Antenna 14.1 (specific OTA sub-channel).
    base_position → right → down → ok → down → ok"""
    logger.info("Launching Antenna 10.1...")
    await base_position()
    await key_right()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_down()
    await key_down()
    await key_down()
    await key_down()
    await key_ok()
    logger.info("Watching Antenna 10.1")
    await asyncio.sleep(WATCH_TIME)


async def open_hdmi():
    """Switch to HDMI input.
    base_position → left x3 → down → ok"""
    logger.info("Switching to HDMI...")
    await base_position()
    for _ in range(3):
        await key_left()
    await key_down()
    await key_ok()
    logger.info("Watching HDMI")
    await asyncio.sleep(WATCH_TIME)


# ==========================================
# ACR Toggle
# Exact sequences from firetv_experiment.sh
# ==========================================

async def toggle_acr_on():
    """Toggle ACR ON.
    base_position → left x5 → down x2 → right x2 → ok →
    down → ok → down x2 → ok → ok → off"""
    logger.info("Toggling ACR ON...")
    await base_position()
    for _ in range(5):
        await key_left()
    for _ in range(3):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_ok()
    await key_down()
    await key_ok()
    for _ in range(2):
        await key_down()
    await key_ok()
    await key_ok()
    await asyncio.sleep(10)
    await power_off()


async def toggle_acr_off():
    """Toggle ACR OFF.
    base_position → left x5 → down x2 → right x2 → ok →
    down → ok → down x2 → ok → off"""
    logger.info("Toggling ACR OFF...")
    await base_position()
    for _ in range(5):
        await key_left()
    for _ in range(3):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_ok()
    await key_down()
    await key_ok()
    for _ in range(2):
        await key_down()
    await key_ok()
    await asyncio.sleep(10)
    await power_off()


# ==========================================
# Exit Helpers
# ==========================================

async def exit_to_home():
    """Generic exit: just go home. FireTV power cycles between
    scenarios so explicit app exit is not needed, but this
    mirrors the Samsung pattern of having exit functions."""
    logger.info("Exiting to home...")
    await go_home()


# ==========================================
# Standalone test
# ==========================================

async def run():
    await connect()
    await go_home()
    await open_fast()


if __name__ == "__main__":
    asyncio.run(run())
