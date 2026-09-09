#TODO: Fix Timings
#TODO: Verify all scenario navigation sequences against actual TCL/Hisense layout
#TODO: Confirm ACR menu path on target device

import subprocess
import socket
import logging
import time
from datetime import datetime
import asyncio


# ==========================================
# Timing Constants
# ==========================================
KEY_DELAY           = 4
BOOT_DELAY          = 30
MAX_BOOT_RETRIES    = 5
BOOT_POLL_INTERVAL  = 10
RUN_CMD_RETRIES     = 10
RUN_CMD_RETRY_WAIT  = 10
#WATCH_TIME          = 10
WATCH_TIME         = 900
#POWER_OFF_WAIT      = 10
POWER_OFF_WAIT     = 120
APP_LAUNCH_WAIT     = 25
NETFLIX_LOAD_WAIT   = 30
#NETFLIX_PREVIEW_WAIT = 10
NETFLIX_PREVIEW_WAIT = 225


# ==========================================
# Google TV / ADB Configuration
# ==========================================
TV_IP   = "192.168.14.136"   # Update to your TCL/Hisense IP
TV_PORT = 5555               # ADB TCP port

SCRIPT = "google_tv.py"


# ==========================================
# Logging
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"google_tv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==========================================
# Low-Level: call google_tv.py via subprocess
# ==========================================

def _run_script(*args) -> tuple[str, bool]:
    """Run python3 google_tv.py <args>, return (output, had_error)."""
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
        "unknown key", "unknown input", "adb error", "failed",
    ])
    return output, has_error


# ==========================================
# Connectivity Check (TCP probe on ADB port 5555)
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
    """Wait for TV's ADB server to become reachable."""
    logger.info("Waiting for TV to become reachable...")
    await asyncio.sleep(BOOT_DELAY)

    for attempt in range(1, MAX_BOOT_RETRIES + 1):
        if is_tv_reachable():
            logger.info("TV is reachable.")
            return True
        if attempt == MAX_BOOT_RETRIES:
            logger.error(f"TV still unreachable after {MAX_BOOT_RETRIES} retries.")
            logger.error("FATAL: TV not reachable. Skipping remaining commands.")
            return False
        logger.warning(f"TV not reachable (attempt {attempt}/{MAX_BOOT_RETRIES}), retrying...")
        await asyncio.sleep(BOOT_POLL_INTERVAL)

    return False


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
                    logger.warning("TV unreachable - waiting for recovery...")
                    if not await wait_for_tv():
                        return False
                else:
                    await asyncio.sleep(RUN_CMD_RETRY_WAIT)
        else:
            if(len(args) > 1 and (args[1] == 'num0' or args[1] == 'num1' or args[1] == 'num2' or args[1] == 'dot' or args[1] == 'num4' or args[1] == 'num7')):
                await asyncio.sleep(0.2)
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
        cmd = ["python3", SCRIPT, "power-state"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.lower()
        if "active" in output or "on" in output:
            return "active"
        if "standby" in output or "off" in output:
            return "standby"
        return None
    except Exception:
        return None


async def power_on():
    state = get_power_state()
    if state == "active":
        logger.info("TV is already ON - skipping power on.")
        return
    logger.info(f"TV state is '{state}' - waking...")
    await run_cmd("on")
    if not await wait_for_tv():
        logger.warning("WARNING: TV did not come up successfully.")


async def power_off():
    state = get_power_state()
    if state != "active":
        logger.info(f"TV is already OFF (state='{state}') - skipping power off.")
        return
    logger.info("TV is ON - sleeping...")
    await run_cmd("off")
    await asyncio.sleep(POWER_OFF_WAIT)
    logger.info("Sleep sent.")


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
    logger.info("Press Back key...")
    await run_cmd("key", "back")

async def key_input():
    logger.info("Press Input key...")
    await run_cmd("key", "input")

async def key_action_menu():
    logger.info("Press Menu key...")
    await run_cmd("key", "menu")

async def key_options():
    logger.info("Press Options/Menu key...")
    await run_cmd("key", "options")

async def set_input_hdmi(port: int = 2):
    """Switch directly to HDMI port via ADB keycode."""
    logger.info(f"Switching to HDMI{port}...")
    await run_cmd("set-input", f"hdmi{port}")


# ==========================================
# App Launcher (ADB direct - faster than nav)
# ==========================================

async def launch_app(app_name: str):
    """Launch an app directly via ADB - more reliable than UI navigation."""
    logger.info(f"Launching {app_name} via ADB...")
    await run_cmd("launch-app", app_name)
    await asyncio.sleep(APP_LAUNCH_WAIT)


# ==========================================
# Base Position
# ==========================================

async def base_position():
    """Navigate to a known base position by pressing HOME 3 times."""
    logger.info("Navigating to base position (home x3)...")
    for _ in range(3):
        await run_cmd("key", "home")


# ==========================================
# Scenario Launchers
# NOTE: Navigation sequences mirror the Sony version.
# Verify and adjust key counts against your specific TCL/Hisense model.
# Where possible, launch_app() is used for reliability over UI navigation.
# ==========================================

async def open_idle():
    """IDLE - sit on home screen."""
    logger.info("Opening IDLE (Home Screen)")
    await base_position()
    await asyncio.sleep(WATCH_TIME)


async def open_fast():
    """Launch FAST via ADB direct launch."""
    logger.info("Launching FAST...")
    await key_down()
    await key_down()
    await key_down()
    for _ in range(6):
        await key_right()
    await key_ok()
    await asyncio.sleep(15)
    await key_ok()
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)



async def open_hdmi():
    """Switch to HDMI 2."""
    logger.info("Switching to HDMI 2...")
    await base_position()
    await key_input()
    await asyncio.sleep(3)
    # Navigate to Antenna in the input list (adjust key_down count for your TV layout)
    await key_right()
    await key_right()
    await key_ok()
    logger.info("Watching HDMI")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_14_1():
    """Antenna 14.1 - use Input key to switch to antenna source."""
    logger.info("Tuning to Antenna 14.1...")
    await base_position()
    
    # Use Input key to select antenna source
    await key_input()
    await asyncio.sleep(3)
    # Navigate to Antenna in the input list (adjust key_down count for your TV layout)
    await key_right()
    await key_ok()
    await asyncio.sleep(5)
    
    # Enter channel number
    await run_cmd("key", "num1")
    await run_cmd("key", "num4")
    #await run_cmd("key", "dot")
    #await run_cmd("key", "num1")
    await key_ok()
    #await run_cmd("key", "ch_up")
    logger.info("Watching Antenna 14.1")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_10_1():
    """Antenna 10.1 - use Input key to switch to antenna source."""
    logger.info("Tuning to Antenna 10.1...")
    await base_position()

    await key_input()
    await asyncio.sleep(3)
    # Navigate to Antenna in the input list (adjust key_down count for your TV layout)
    await key_right()
    await key_ok()
    await asyncio.sleep(5)

    await run_cmd("key", "num1")
    await run_cmd("key", "num0")
    
    #await run_cmd("key", "dot")
    #await run_cmd("key", "num1")
    await key_ok()
    logger.info("Watching Antenna 10.1")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna():
    """Antenna 7.2 (DEFY) - use Input key to switch to antenna source."""
    logger.info("Tuning to Antenna 7.2 (DEFY)...")
    await base_position()

    await key_input()
    await asyncio.sleep(3)
    # Navigate to Antenna in the input list (adjust key_down count for your TV layout)
    await key_right()
    await key_ok()
    await asyncio.sleep(5)

    await run_cmd("key", "num7")
    #await run_cmd("key", "dot")
    #await run_cmd("key", "num2")
    #await key_ok()
    logger.info("Watching Antenna 7.2 (DEFY)")
    await asyncio.sleep(WATCH_TIME)


async def open_netflix():
    """Launch Netflix via ADB direct launch."""
    logger.info("Launching Netflix...")
    await launch_app("netflix")
    await key_right()
    for _ in range(4):
        logger.info("Watching Netflix")
        await asyncio.sleep(NETFLIX_PREVIEW_WAIT)
        for _ in range(11):
            await key_left()


async def open_youtube():
    """Launch YouTube via ADB direct launch."""
    logger.info("Launching YouTube...")
    await launch_app("youtube")
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
    """Launch Tubi via ADB direct launch."""
    logger.info("Launching Tubi...")
    await launch_app("tubi")
    await key_ok()
    await asyncio.sleep(15)
    await key_ok()
    logger.info("Watching Tubi")
    await asyncio.sleep(WATCH_TIME)
    for _ in range(6):
        await key_back()


# ==========================================
# Exit Helpers
# ==========================================

async def exit_to_home():
    logger.info("Exiting to home...")
    await go_home()
