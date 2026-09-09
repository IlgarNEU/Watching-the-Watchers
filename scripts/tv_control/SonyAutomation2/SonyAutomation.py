#TODO: Fix Timings
#TODO: Verify all scenario navigation sequences against actual KD-32W830K
#TODO: Confirm ACR menu path on KD-32W830K

import subprocess
import socket
import logging
import time
from datetime import datetime
import asyncio


# ==========================================
# Timing Constants
# ==========================================
KEY_DELAY = 4
BOOT_DELAY = 25         # REST server takes a few seconds to come up after WoL
MAX_BOOT_RETRIES = 5
BOOT_POLL_INTERVAL = 10
RUN_CMD_RETRIES = 10
RUN_CMD_RETRY_WAIT = 10
#WATCH_TIME = 10
WATCH_TIME = 900
#POWER_OFF_WAIT = 10
POWER_OFF_WAIT = 120
APP_LAUNCH_WAIT = 25
NETFLIX_LOAD_WAIT = 40
#NETFLIX_PREVIEW_WAIT = 10
NETFLIX_PREVIEW_WAIT = 225


# ==========================================
# Sony Bravia Configuration
# ==========================================
TV_IP   = "192.168.14.140"        # KD-32W830K IP
TV_PORT = 80                      # REST API port (not 20060 - that's SSIP/BF1 only)
TV_MAC  = "88:C9:E8:78:BE:7B"    # KD-32W830K MAC (from getSystemInformation)

SCRIPT = "bravia.py"


# ==========================================
# Logging
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"sony_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==========================================
# Low-Level: call bravia.py via subprocess
# ==========================================

def _run_script(*args) -> tuple[str, bool]:
    """Run python3 bravia.py <args>, return (output, had_error)."""
    cmd = ["python3", SCRIPT] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout + " " + result.stderr).strip()
    except subprocess.TimeoutExpired:
        output = "timed out"
    except Exception as e:
        output = str(e)

    has_error = any(kw in output.lower() for kw in [
        "timed out", "no route to host", "connection refused",
        "network is unreachable", "no answer", "got no answer",
        "unknown key", "unknown input"
    ])
    return output, has_error


# ==========================================
# Connectivity Check (TCP probe on port 80)
# ==========================================

def is_tv_reachable() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        return s.connect_ex((TV_IP, TV_PORT)) == 0
    except Exception:
        return False
    finally:
        s.close()


async def wait_for_tv() -> bool:
    """Wait for TV's REST server to become reachable."""
    logger.info("Waiting for TV to become reachable...")
    await asyncio.sleep(BOOT_DELAY)

    attempt = 1
    while not is_tv_reachable():
        if attempt >= MAX_BOOT_RETRIES:
            logger.error(f"TV still unreachable after {MAX_BOOT_RETRIES} retries - re-sending on...")
            _run_script("on")
            await asyncio.sleep(BOOT_DELAY)
            if not is_tv_reachable():
                logger.error("FATAL: TV not reachable. Skipping remaining commands.")
                return False
            return True
        logger.warning(f"TV not reachable (attempt {attempt}/{MAX_BOOT_RETRIES}) - re-sending on...")
        _run_script("on")
        await asyncio.sleep(BOOT_POLL_INTERVAL)
        attempt += 1

    logger.info("TV is reachable.")
    return True


# ==========================================
# Robust Command Execution
# ==========================================

async def run_cmd(*args):
    for attempt in range(1, RUN_CMD_RETRIES + 1):
        output, has_error = _run_script(*args)
        if has_error:
            logger.warning(f"Command failed (attempt {attempt}/{RUN_CMD_RETRIES}): {' '.join(args)} - {output}")
            if attempt < RUN_CMD_RETRIES:
                if not is_tv_reachable():
                    logger.warning("TV unreachable - attempting recovery...")
                    if not await wait_for_tv():
                        return False
                else:
                    await asyncio.sleep(RUN_CMD_RETRY_WAIT)
        else:
            await asyncio.sleep(KEY_DELAY)
            return True
    logger.error(f"Command failed after {RUN_CMD_RETRIES} retries: {' '.join(args)}")
    await asyncio.sleep(KEY_DELAY)
    return False


# ==========================================
# Power Control
# ==========================================

def get_power_state() -> str | None:
    """Return 'active', 'standby', or None if unreachable."""
    try:
        cmd = ["python3", SCRIPT, "raw", "system", "getPowerStatus"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        import json as _json
        data = _json.loads(result.stdout)
        return data["result"][0]["status"]
    except Exception:
        return None


async def power_on():
    state = get_power_state()
    if state == "active":
        logger.info("TV is already ON - skipping power on.")
        return
    logger.info(f"TV state is '{state}' - powering on...")
    await run_cmd("on")
    if not await wait_for_tv():
        logger.warning("WARNING: TV did not come up successfully.")


async def power_off():
    state = get_power_state()
    if state != "active":
        logger.info(f"TV is already OFF (state='{state}') - skipping power off.")
        return
    logger.info("TV is ON - powering off...")
    await run_cmd("off")
    await asyncio.sleep(POWER_OFF_WAIT)
    logger.info("Power off sent.")


# ==========================================
# Navigation Helpers
# ==========================================

async def go_home():
    logger.info("Going home...")
    await run_cmd("key", "home")


async def key_up():
    logger.info("Press Up key...")
    await run_cmd("key", "up")


async def key_down():
    logger.info("Press Down key...")
    await run_cmd("key", "down")


async def key_left():
    logger.info("Press Left key...")
    await run_cmd("key", "left")


async def key_right():
    logger.info("Press Right key...")
    await run_cmd("key", "right")


async def key_ok():
    logger.info("Press OK/Confirm key...")
    await run_cmd("key", "confirm")


async def key_back():
    logger.info("Press Back/Return key...")
    await run_cmd("key", "return")


async def key_input():
    logger.info("Press Input key...")
    await run_cmd("key", "input")


async def key_action_menu():
    logger.info("Press Action Menu key...")
    await run_cmd("key", "action_menu")


async def key_options():
    logger.info("Press Options key...")
    await run_cmd("key", "options")


async def set_input_hdmi(port: int = 2):
    """Switch directly to HDMI port via REST API set-input."""
    logger.info(f"Switching to HDMI{port}...")
    await run_cmd("set-input", f"hdmi{port}")


# ==========================================
# Base Position
#   Press HOME 3 times to land on a known starting point.
# ==========================================

async def base_position():
    """Navigate to the known base position by pressing HOME 3 times."""
    logger.info("Navigating to base position (home x3)...")
    for _ in range(8):
        await run_cmd("key", "home")


# ==========================================
# Scenario Launchers
# ==========================================

async def open_idle():
    """IDLE - sit on home screen, no navigation."""
    logger.info("Opening IDLE (Home Screen)")
    await base_position()
    await asyncio.sleep(WATCH_TIME)


async def open_fast():
    """Launch FAST.
    base_position -> down x3 -> ok -> wait -> ok"""
    logger.info("Launching FAST...")
    await base_position()
    for _ in range(3):
        await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)
    await key_back()
    await key_back()


async def open_hdmi():
    """Switch to HDMI 2 via REST API set-input."""
    logger.info("Switching to HDMI 2...")
    await base_position()
    await set_input_hdmi(2)
    await asyncio.sleep(5)
    logger.info("Watching HDMI")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_14_1():
    """Tune directly to Antenna 14.1 via REST API URI."""
    logger.info("Tuning to Antenna 14.1...")
    await run_cmd("raw", "avContent", "setPlayContent",
                  '[{"uri":"tv:atsct?dispNum=14.1&trip=0.0.14&srvName=HDTV1"}]')
    await asyncio.sleep(5)
    logger.info("Watching Antenna 14.1")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_10_1():
    """Tune directly to Antenna 10.1 via REST API URI."""
    logger.info("Tuning to Antenna 10.1...")
    await run_cmd("raw", "avContent", "setPlayContent",
                  '[{"uri":"tv:atsct?dispNum=10.1&trip=0.0.14&srvName=HDTV1"}]')
    await asyncio.sleep(5)
    logger.info("Watching Antenna 10.1")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna():
    """Tune directly to Antenna 7.2 (DEFY) via REST API URI."""
    logger.info("Tuning to Antenna 7.2 (DEFY)...")
    await run_cmd("raw", "avContent", "setPlayContent",
                  '[{"uri":"tv:atsct?dispNum=7.2&trip=0.0.4&srvName=DEFY"}]')
    await asyncio.sleep(5)
    logger.info("Watching Antenna 7.2 (DEFY)")
    await asyncio.sleep(WATCH_TIME)


async def open_netflix():
    """Launch Netflix.
    base_position -> down x3 -> right -> ok -> wait -> right -> loop previews"""
    logger.info("Launching Netflix...")
    await base_position()
    for _ in range(3):
        await key_down()
    await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_right()
    for _ in range(4):
        logger.info("Watching Netflix")
        await asyncio.sleep(NETFLIX_PREVIEW_WAIT)
        for _ in range(11):
            await key_left()


async def open_youtube():
    """Launch YouTube.
    base_position -> down x3 -> right x2 -> ok -> wait -> navigate"""
    logger.info("Launching YouTube...")
    await base_position()
    for _ in range(3):
        await key_down()
    await key_right()
    await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await key_back()
    await key_left()
    await key_left()
    await key_left()
    await key_up()
    await key_ok()
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
    for _ in range(6):
        await key_back()


async def open_tubi():
    """Launch Tubi.
    base_position -> down x3 -> right x4 -> ok -> wait -> ok -> wait 15 -> ok"""
    logger.info("Launching Tubi...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(4):
        await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await asyncio.sleep(15)
    await key_ok()
    logger.info("Watching Tubi")
    await asyncio.sleep(WATCH_TIME)
    for _ in range(6):
        await key_back()


# ==========================================
# ACR Toggle (separate ON/OFF)
# ==========================================

async def toggle_acr_off():
    """Disable ACR.
    base_position -> right x5 -> ok -> ok ->
    down x6 -> right -> down x14 -> right -> down -> ok"""
    logger.info("Toggling ACR OFF...")
    await base_position()
    for _ in range(5):
        await key_right()
    await key_ok()
    await key_ok()
    for _ in range(6):
        await key_down()
    await key_right()
    for _ in range(14):
        await key_down()
    await key_right()
    await key_down()
    await key_ok()


async def toggle_acr_on():
    """Enable ACR. Same as toggle_acr_off, then sleep 5 -> ok -> ok."""
    logger.info("Toggling ACR ON...")
    await toggle_acr_off()
    await asyncio.sleep(5)
    await key_ok()
    await key_ok()
    await asyncio.sleep(5)


# ==========================================
# Exit Helpers
# ==========================================

async def exit_to_home():
    logger.info("Exiting to home...")
    await go_home()