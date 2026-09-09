#TODO: Fix Timings
#TODO: Fix IP address and MAC
#TODO: Verify all scenario navigation sequences against actual BF1
#TODO: Confirm ACR menu path on Bravia BF1

import subprocess
import socket
import logging
import time
from datetime import datetime
import asyncio


# ==========================================
# Timing Constants
# ==========================================
KEY_DELAY = 3
BOOT_DELAY = 15         # SSIP server takes a few seconds to come up after WoL
MAX_BOOT_RETRIES = 5
BOOT_POLL_INTERVAL = 10
RUN_CMD_RETRIES = 10
RUN_CMD_RETRY_WAIT = 10
WATCH_TIME = 300
WATCH_TIME_2 = 150
POWER_OFF_WAIT = 20
APP_LAUNCH_WAIT = 25
NETFLIX_LOAD_WAIT = 40
NETFLIX_PREVIEW_WAIT =75


# ==========================================
# Sony Bravia Configuration
# ==========================================
TV_IP = "192.168.14.133"           # Update to your BF1's IP
TV_PORT = 20060                  # SSIP fixed port
TV_MAC = "58:18:62:30:2F:EB"     # Get from TV: View Network Status

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
# Connectivity Check (TCP probe on SSIP port 20060)
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
    """Wait for TV's SSIP server to become reachable."""
    logger.info("Waiting for TV to become reachable...")
    await asyncio.sleep(BOOT_DELAY)

    attempt = 1
    while not is_tv_reachable():
        if attempt >= MAX_BOOT_RETRIES:
            logger.error(f"TV still unreachable after {MAX_BOOT_RETRIES} retries — re-sending WoL...")
            _run_script("on")
            await asyncio.sleep(BOOT_DELAY)
            if not is_tv_reachable():
                logger.error("FATAL: TV not reachable. Skipping remaining commands.")
                return False
            return True
        logger.warning(f"TV not reachable (attempt {attempt}/{MAX_BOOT_RETRIES}) — re-sending WoL...")
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
            logger.warning(f"Command failed (attempt {attempt}/{RUN_CMD_RETRIES}): {' '.join(args)} — {output}")
            if attempt < RUN_CMD_RETRIES:
                if not is_tv_reachable():
                    logger.warning("TV unreachable — attempting recovery...")
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

async def power_on():
    logger.info("Waking Sony Bravia TV...")
    await run_cmd("on")
    if not await wait_for_tv():
        logger.warning("WARNING: TV did not come up successfully.")


async def power_off():
    logger.info("Powering off Sony Bravia TV...")
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


async def set_input_hdmi(port: int = 1):
    """Switch directly to HDMI port via dedicated IRCC key (no menu nav)."""
    logger.info(f"Switching to HDMI{port} via IRCC...")
    await run_cmd("key", f"hdmi{port}")


# ==========================================
# Base Position
#   Press HOME 8 times to land on a known starting point.
# ==========================================

async def base_position():
    """Navigate to the known base position by pressing HOME 8 times."""
    logger.info("Navigating to base position (home x8)...")
    for _ in range(8):
        await run_cmd("key", "home")


# ==========================================
# Scenario Launchers
# Exact sequences from user's BF1 hardcoded paths.
# ==========================================

async def open_idle():
    """IDLE — sit on home screen, no navigation."""
    logger.info("Opening IDLE (Home Screen)")
    await base_position()
    await asyncio.sleep(WATCH_TIME)


async def open_fast():
    """Launch FAST.
    base_position → down × 3 → right × 3 → ok → ok"""
    logger.info("Launching FAST...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(3):
        await key_right()
    await key_ok()
    await key_ok()
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)
    

async def open_hdmi():
    """Switch to HDMI 1 via dedicated IRCC key.
    base_position → key hdmi1"""
    logger.info("Switching to HDMI 1...")
    await base_position()
    await set_input_hdmi(1)
    await asyncio.sleep(5)
    logger.info("Watching HDMI")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_14_1():
    """Antenna 14.1.
    base_position → down × 3 → right × 4 → ok"""
    logger.info("Tuning to Antenna 14.1...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(4):
        await key_right()
    await key_ok()
    await asyncio.sleep(5)
    await run_cmd("key", "num1")
    await run_cmd("key", "num4")
    await run_cmd("key", "dot")
    await run_cmd("key", "num1")
    await key_ok()
    logger.info("Watching Antenna 14.1")
    await asyncio.sleep(WATCH_TIME)

async def open_antenna_10_1():
    """Antenna 14.1.
    base_position → down × 3 → right × 4 → ok"""
    logger.info("Tuning to Antenna 10.1...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(4):
        await key_right()
    await key_ok()
    await asyncio.sleep(5)
    await run_cmd("key", "num1")
    await run_cmd("key", "num0")
    await run_cmd("key", "dot")
    await run_cmd("key", "num1")
    await key_ok()
    logger.info("Watching Antenna 10.1")
    await asyncio.sleep(WATCH_TIME)

async def open_antenna():
    """Antenna (random).
    base_position → down × 3 → right × 4 → ok
    (same path as Antenna 14.1 — selects whatever the antenna tile points at)"""
    logger.info("Tuning to Antenna (random)...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(4):
        await key_right()
    await key_ok()
    await asyncio.sleep(5)
    await run_cmd("key", "num7")
    await run_cmd("key", "dot")
    await run_cmd("key", "num1")
    await key_ok()
    logger.info("Watching Antenna")
    await asyncio.sleep(WATCH_TIME)


async def open_netflix():
    """Launch Netflix.
    base_position → down × 3 → right → ok →
    sleep APP_LAUNCH_WAIT → sleep 30 → right → sleep 300 → left × 5"""
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
    base_position → down × 3 → ok → sleep 10"""
    logger.info("Launching YouTube...")
    await base_position()
    for _ in range(3):
        await key_down()
    await key_ok()
    await asyncio.sleep(10)
    await key_ok()
    await key_back()
    await key_left()
    await key_left()
    await key_left()
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
    for _ in range(6):
        await key_back()

async def open_tubi():
    """Launch Tubi.
    base_position → down × 3 → right × 2 → ok →
    sleep APP_LAUNCH_WAIT → ok → ok"""
    logger.info("Launching Tubi...")
    await base_position()
    for _ in range(3):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await key_ok()
    logger.info("Watching Tubi")
    await asyncio.sleep(WATCH_TIME)
    for _ in range(6):
        await key_back()

# ==========================================
# ACR Toggle (separate ON/OFF — Vizio-style)
# Exact sequences from user's BF1 hardcoded paths.
# ==========================================

async def toggle_acr_off():
    """Disable ACR.
    base_position → right × 5 → ok → ok →
    down × 6 → right →
    down × 13 → right →
    down → ok"""
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
    """Enable ACR.
    Same as toggle_acr_off, then sleep 5 → ok → ok."""
    logger.info("Toggling ACR ON...")
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


# ==========================================
# Standalone test
# ==========================================
