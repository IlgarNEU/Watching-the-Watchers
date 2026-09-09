import asyncio
from aiowebostv import WebOsClient
import wakeonlan
import logging
import aiohttp
import time
from datetime import datetime

TV_IP = "192.168.14.119"
TV_MAC = "00:A1:59:8F:AB:38"
CLIENT_KEY = "fb95eaa2913aed10b13d0fc38c3f693b"

OFF_TIME = 20
BOOT_TIME = 40
WATCH_TIME = 300
IDLE_TIME = 75
NETFLIX_TIME = 75

TV_BROADCAST = "192.168.14.255"

NETFLIX = "netflix"
YOUTUBE = "youtube.leanback.v4"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"lg_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def wake_tv(attempts=5, delay=2):
    """Send multiple WoL packets for reliability"""
    logger.info(f"Sending {attempts} WoL packets...")
    for i in range(attempts):
        wakeonlan.send_magic_packet(TV_MAC, ip_address=TV_BROADCAST)
        logger.info(f"WoL packet {i+1}/{attempts} sent.")
        time.sleep(delay)


async def is_tv_reachable():
    """Simple TCP check on WebOS WebSocket port"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(TV_IP, 3000), timeout=3
        )
        writer.close()
        await writer.wait_closed()
        logger.info("TV reachable.")
        return True
    except Exception:
        logger.warning("TV not reachable.")
        return False


async def connect(retries=100):
    """Connect with reachability check — no WoL here"""
    for attempt in range(retries):
        try:
            logger.info(f"Connecting (attempt {attempt+1}/{retries})...")

            reachable = await is_tv_reachable()
            if not reachable:
                logger.warning("TV not reachable, waiting 10s...")
                await asyncio.sleep(10)
                continue

            client = WebOsClient(TV_IP, client_key=CLIENT_KEY)
            await asyncio.wait_for(client.connect(), timeout=15)
            logger.info("Connected!")
            return client

        except asyncio.TimeoutError:
            logger.warning(f"Connection timed out (attempt {attempt+1})")
        except Exception as e:
            logger.warning(f"Connection failed (attempt {attempt+1}): {e}")

        await asyncio.sleep(10)

    raise Exception("Could not connect after all retries.")


async def power_on():
    """WoL only here, not in connect()"""
    logger.info("Turning ON TV via WoL...")
    wake_tv(attempts=5, delay=2)
    await asyncio.sleep(BOOT_TIME)

    # If still not reachable, send more WoL bursts
    for attempt in range(100):
        if await is_tv_reachable():
            break
        logger.warning(f"TV still not reachable, sending WoL burst again ({attempt+1}/5)...")
        wake_tv(attempts=3, delay=2)
        await asyncio.sleep(40)

    client = await connect()
    return client


async def power_off(client):
    logger.info("Powering off TV...")
    try:
        await client.power_off()
    except Exception as e:
        logger.warning(f"power_off error: {e}")
    await asyncio.sleep(OFF_TIME)


async def safe_button(client, button, delay=2, retries=3):
    """Send button with auto-reconnect — always returns client"""
    for attempt in range(retries):
        try:
            await client.button(button)
            logger.info(f"Button: {button}")
            await asyncio.sleep(delay)
            return client
        except Exception as e:
            logger.warning(f"Button {button} failed (attempt {attempt+1}): {e}")
            await asyncio.sleep(5)
            client = await connect()
    raise Exception(f"Failed to send {button} after {retries} retries.")


async def safe_sleep(client, duration, chunk=240):
    """Sleep in chunks, reconnecting every chunk seconds to keep connection alive"""
    elapsed = 0
    while elapsed < duration:
        sleep_time = min(chunk, duration - elapsed)
        await asyncio.sleep(sleep_time)
        elapsed += sleep_time
        logger.info(f"Slept {elapsed}/{duration}s")
        try:
            await client.get_current_app()
            logger.info("Connection alive.")
        except asyncio.CancelledError:
            logger.warning("Connection dropped (CancelledError), reconnecting...")
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(5)
            client = await connect()
        except Exception as e:
            logger.warning(f"Connection lost, reconnecting: {e}")
            client = await connect()
    return client


# ─── Key helpers — all return client ─────────────────────────────────────

async def key_left(client):
    return await safe_button(client, "LEFT")

async def key_right(client):
    return await safe_button(client, "RIGHT")

async def key_up(client):
    return await safe_button(client, "UP")

async def key_down(client):
    return await safe_button(client, "DOWN")

async def key_select(client):
    return await safe_button(client, "ENTER")

async def key_back(client):
    return await safe_button(client, "BACK")

async def key_home(client):
    return await safe_button(client, "HOME")

async def go_home(client):
    logger.info("Going home...")
    for _ in range(3):
        client = await key_home(client)
    return client


# ─── App functions — all return client ───────────────────────────────────

async def open_netflix(client):
    client = await go_home(client)
    logger.info("Launching Netflix...")
    await client.launch_app(NETFLIX)
    await asyncio.sleep(20)
    for _ in range(4):
        client = await safe_sleep(client, NETFLIX_TIME)
        client = await connect()
        for _ in range(13):
            client = await key_left(client)
    return client


async def open_youtube(client):
    client = await go_home(client)
    logger.info("Opening YouTube...")
    await client.launch_app(YOUTUBE)
    await asyncio.sleep(20)
    client = await connect()
    client = await key_select(client)
    await asyncio.sleep(5)
    client = await key_back(client)
    client = await key_up(client)
    client = await key_select(client)
    await asyncio.sleep(3)
    for _ in range(10):
        client = await key_right(client)
    for _ in range(7):
        client = await key_left(client)
    for _ in range(5):
        client = await key_down(client)
    client = await key_select(client)
    client = await safe_sleep(client, WATCH_TIME)
    return client


async def open_tubi(client):
    client = await go_home(client)
    logger.info("Opening Tubi...")
    for _ in range(10):
        client = await key_right(client)
    client = await key_select(client)
    await asyncio.sleep(20)
    client = await connect()
    client = await key_left(client)
    client = await key_up(client)
    client = await key_select(client)
    await asyncio.sleep(3)
    for _ in range(7):
        client = await key_right(client)
    client = await key_select(client)
    await asyncio.sleep(3)
    client = await key_select(client)
    await asyncio.sleep(3)
    client = await safe_sleep(client, WATCH_TIME)
    return client


async def open_hdmi(client):
    client = await go_home(client)
    logger.info("Opening HDMI...")
    await client.set_input("HDMI_1")
    client = await safe_sleep(client, WATCH_TIME)
    return client


async def toggle_acr(client):
    client = await go_home(client)
    logger.info("Toggling ACR...")
    for _ in range(2):
        client = await key_up(client)
    client = await key_left(client)
    for _ in range(2):
        client = await key_down(client)
    client = await key_select(client)
    client = await key_select(client)
    await asyncio.sleep(10)
    client = await connect()
    for _ in range(2):
        client = await key_down(client)
    client = await key_right(client)
    for _ in range(7):
        client = await key_down(client)
    client = await key_right(client)
    for _ in range(4):
        client = await key_down(client)
    client = await key_right(client)
    for _ in range(6):
        client = await key_down(client)
    client = await key_select(client)
    await asyncio.sleep(10)
    return client


async def open_fast(client):
    client = await go_home(client)
    logger.info("Opening FAST...")
    client = await key_right(client)
    client = await key_select(client)
    await asyncio.sleep(20)
    client = await connect()
    client = await key_left(client)
    client = await key_down(client)
    client = await key_select(client)
    await asyncio.sleep(3)
    client = await key_select(client)
    logger.info("Watching FAST...")
    client = await safe_sleep(client, WATCH_TIME)
    return client


async def exit_anything(client):
    logger.info("Exiting...")
    for _ in range(3):
        client = await key_home(client)
    client = await key_back(client)
    client = await key_up(client)
    client = await key_select(client)
    client = await key_home(client)
    return client


async def open_antenna(client):
    client = await go_home(client)
    logger.info("Opening Antenna...")
    await client.launch_app("com.webos.app.livetv")
    await asyncio.sleep(20)
    client = await connect()
    client = await safe_button(client, "CHANNELUP")
    await asyncio.sleep(2)
    client = await safe_button(client, "CHANNELUP")
    await asyncio.sleep(2)
    client = await safe_sleep(client, WATCH_TIME)
    client = await safe_button(client, "CHANNELDOWN")
    await asyncio.sleep(2)
    client = await safe_button(client, "CHANNELDOWN")

    await asyncio.sleep(2)
    return client


async def open_antenna_custom(client):
    client = await go_home(client)
    logger.info("Opening Antenna Custom 10.1...")
    await client.launch_app("com.webos.app.livetv")
    await asyncio.sleep(20)
    client = await connect()
    client = await safe_sleep(client, WATCH_TIME)
    return client

async def open_antenna_custom_2(client):
    client = await go_home(client)
    logger.info("Opening Antenna Custom2 14.1...")
    await client.launch_app("com.webos.app.livetv")
    await asyncio.sleep(20)
    client = await connect()
    client = await safe_button(client, "CHANNELUP")
    client = await safe_sleep(client, WATCH_TIME)
    client = await safe_button(client, "CHANNELDOWN")
    await asyncio.sleep(2)
    return client


async def open_idle(client):
    client = await go_home(client)
    logger.info("Opening IDLE...")
    client = await go_home(client)
    for _ in range(4):
        client = await safe_sleep(client, IDLE_TIME)
        client = await go_home(client)
    return client
