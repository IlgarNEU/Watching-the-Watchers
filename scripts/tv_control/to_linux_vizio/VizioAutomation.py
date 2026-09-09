#TODO: Fix Timings
#TODO: Fix IP address and MAC

import subprocess
import socket
import logging
import time
from datetime import datetime
import asyncio


# ==========================================
# Timing Constants (match test.sh)
# ==========================================
KEY_DELAY = 3           # Seconds between button presses
BOOT_DELAY = 40         # Seconds for initial TV boot wait
MAX_BOOT_RETRIES = 5    # Max WoL retries if TV doesn't come up
BOOT_POLL_INTERVAL = 10 # Seconds between reachability checks
RUN_CMD_RETRIES = 3     # Retries per key command on failure
RUN_CMD_RETRY_WAIT = 5  # Seconds between key command retries
WATCH_TIME = 900         # Seconds per scenario (SCENARIO_DURATION)
POWER_OFF_WAIT = 120     # Seconds after power off before next on
APP_LAUNCH_WAIT = 20    # Seconds to let an app fully load
NETFLIX_LOAD_WAIT = 40  # Seconds for Netflix to load after launch
NETFLIX_PREVIEW_WAIT = 300  # Seconds Netflix plays preview


# ==========================================
# Vizio Configuration
# ==========================================
TV_IP = "192.168.14.120"
# TV_IP = "10.19.37.243"
TV_PORT = 7345
TV_MAC = "14:C6:7D:15:31:56"

SCRIPT = "test.py"      # Path to the Vizio SmartCast CLI


# ==========================================
# Logging
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"vizio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==========================================
# Low-Level: call test.py via subprocess
# ==========================================

def _run_script(*args) -> tuple[str, bool]:
    """Run python3 test.py <args>, return (output, had_error)."""
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
        "network is unreachable"
    ])
    return output, has_error


# ==========================================
# Connectivity Check (TCP probe, matches test.sh)
# ==========================================

def is_tv_reachable() -> bool:
    """Quick TCP probe on the SmartCast API port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        return s.connect_ex((TV_IP, TV_PORT)) == 0
    except Exception:
        return False
    finally:
        s.close()


async def wait_for_tv() -> bool:
    """Wait for TV to become reachable. Mirrors test.sh wait_for_tv."""
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
# Robust Command Execution (mirrors test.sh run_cmd)
# ==========================================

async def run_cmd(*args):
    """Run a test.py command with retry logic matching test.sh run_cmd."""
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
    """Turn on TV via WoL (test.py on) + wait."""
    logger.info("Waking Vizio TV...")
    await run_cmd("on")
    if not await wait_for_tv():
        logger.warning("WARNING: TV did not come up successfully.")


async def power_off():
    """Turn off TV (test.py off)."""
    logger.info("Powering off Vizio TV...")
    await run_cmd("off")
    await asyncio.sleep(POWER_OFF_WAIT)
    logger.info("Power off sent.")


# ==========================================
# Navigation Helpers
# ==========================================

async def go_home():
    logger.info("Going home...")
    await run_cmd("key", "home")
    await run_cmd("key", "ok")


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
    logger.info("Press OK key...")
    await run_cmd("key", "ok")


async def key_back():
    logger.info("Press Back key...")
    await run_cmd("key", "back")


async def key_menu():
    logger.info("Press Menu key...")
    await run_cmd("key", "menu")


async def key_smartcast():
    logger.info("Press SmartCast key...")
    await run_cmd("key", "smartcast")


async def key_input_cycle():
    logger.info("Cycling input...")
    await run_cmd("input-cycle")


# ==========================================
# Scenario Launchers
# Exact sequences from test.sh run_all
# ==========================================

async def open_idle():
    """IDLE — sit on home screen, no navigation.
    test.sh: run_scenario "IDLE" (nothing before it)"""
    logger.info("Opening IDLE (Home Screen)")
    for _ in range(3):
        await asyncio.sleep(WATCH_TIME // 3)
        await run_cmd("key", "home")





async def open_fast():
    """Launch FAST channels.
    test.sh: input-cycle → down → ok → sleep 20 →
    left × 2 → up × 2 → ok → sleep 20 → down → ok → ok"""
    logger.info("Launching FAST...")
    await key_input_cycle()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    for _ in range(2):
        await key_left()
    for _ in range(2):
        await key_up()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_down()
    await key_ok()
    await key_ok()
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)


async def open_hdmi():
    """Switch to HDMI.
    test.sh: input-cycle → down × 3 → ok"""
    logger.info("Switching to HDMI...")
    await key_input_cycle()
    for _ in range(2):
        await key_down()
    await key_ok()
    logger.info("Watching HDMI")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna_10_1():
    """Launch Antenna 14.1.
    test.sh: smartcast → down → ok → left → down × 3 → right × 2 → ok"""
    logger.info("Launching Antenna 10.1...")
    await key_smartcast()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_left()
    for _ in range(3):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_ok()
    logger.info("Watching Antenna 10.1")
    await asyncio.sleep(WATCH_TIME)

async def open_antenna_14_1():
    """Launch Antenna 14.1.
    test.sh: smartcast → down → ok → left → down × 3 → right × 2 → ok"""
    logger.info("Launching Antenna 14.1...")
    await key_smartcast()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_left()
    for _ in range(3):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_down()
    await key_ok()
    logger.info("Watching Antenna 14.1")
    await asyncio.sleep(WATCH_TIME)


async def open_antenna():
    """Launch Antenna (random channel).
    test.sh: smartcast → down → ok → left → down × 3 → right → down → right → ok"""
    logger.info("Launching Antenna (random)...")
    await key_smartcast()
    await key_down()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_left()
    for _ in range(3):
        await key_down()
    await key_right()
    await key_down()
    await key_down()
    await key_right()
    await key_ok()
    logger.info("Watching Antenna")
    await asyncio.sleep(WATCH_TIME)


async def open_netflix():
    """Launch Netflix.
    test.sh: down × 2 → ok → sleep 40 → left → sleep 360 → left × 5"""
    logger.info("Launching Netflix...")
    for _ in range(2):
        await key_down()
    await key_ok()
    await asyncio.sleep(NETFLIX_LOAD_WAIT)
    await key_left()
    #await asyncio.sleep(NETFLIX_PREVIEW_WAIT)
    for _ in range(4):
        logger.info("Watching Netflix")
        await asyncio.sleep(WATCH_TIME // 4)
        for _ in range(10):
            await key_left()



async def open_youtube():
    """Launch YouTube.
    test.sh: down × 2 → right → ok → sleep 20 →
    left → up → right → down × 8 → ok"""
    logger.info("Launching YouTube...")
    for _ in range(2):
        await key_down()
    await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_left()
    await key_up()
    await key_right()
    for _ in range(8):
        await key_down()
    await key_ok()
    logger.info("Watching YouTube")
    await asyncio.sleep(WATCH_TIME)


async def open_tubi():
    """Launch Tubi.
    test.sh: down × 2 → right × 2 → ok → sleep 20 → ok → ok"""
    logger.info("Launching Tubi...")
    for _ in range(2):
        await key_down()
    for _ in range(2):
        await key_right()
    await key_ok()
    await asyncio.sleep(APP_LAUNCH_WAIT)
    await key_ok()
    await key_ok()
    logger.info("Watching Tubi")
    await asyncio.sleep(WATCH_TIME)


# ==========================================
# ACR Toggle (single toggle, not on/off)
# Exact sequence from test.sh toggle_acr
# ==========================================

async def toggle_acr_off():
    """Toggle ACR OFF.
    test.sh toggle_acr_off:
    down → left → down × 8 → ok → up → ok → up × 2 → ok → down × 5 → left"""
    logger.info("Toggling ACR OFF...")
    await key_down()
    await key_left()
    for _ in range(8):
        await key_down()
    await key_ok()
    await key_up()
    await key_ok()
    for _ in range(2):
        await key_up()
    await key_ok()
    for _ in range(5):
        await key_down()
    await key_left()
    await asyncio.sleep(10)


async def toggle_acr_on():
    """Toggle ACR ON.
    test.sh toggle_acr_on:
    down → left → down × 8 → ok → up → ok → up × 2 → ok → down × 5 → left →
    right → ok → sleep 5"""
    logger.info("Toggling ACR ON...")
    await key_down()
    await key_left()
    for _ in range(8):
        await key_down()
    await key_ok()
    await key_up()
    await key_ok()
    for _ in range(2):
        await key_up()
    await key_ok()
    for _ in range(5):
        await key_down()
    await key_left()
    await asyncio.sleep(5)
    await key_right()
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

async def run():
    await go_home()
    await open_fast()


if __name__ == "__main__":
    asyncio.run(run())
