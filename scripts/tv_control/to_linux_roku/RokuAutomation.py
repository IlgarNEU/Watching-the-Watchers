#TODO: FIX THE IP ADDRESS
#TODO: TEST HDMI AND SCREENCAST
#TODO: Write ScreenCast
#TODO: Fix times of delays, etc
#TODO: Fix Youtube Search
#TODO: ADD delay for selects


import asyncio
import aiohttp
import logging
from datetime import datetime

OFF_TIME = 120       #The duration TV stays OFF
BOOT_TIME = 15      #The duration needed after turning on
WATCH_TIME = 900     #The duration needed to watch each scenario
IDLE_TIME = 225      #The duration needed to stay IDLE and repeat N times
NETFLIX_TIME = 225   #The duration needed to wait until trailer ends and go back N times

TV_IP = "192.168.14.129"

NETFLIX = "12"
YOUTUBE = "837"
TUBI = "41468"
FAST = "151908"

async def list_apps():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{TV_IP}:8060/query/apps") as resp:
            print(await resp.text())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"roku_roku_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def send_key(key, delay=2):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"http://{TV_IP}:8060/keypress/{key}") as resp:
            logger.info(f"Key: {key} | Status: {resp.status}")
    await asyncio.sleep(delay)


async def get_active_app():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{TV_IP}:8060/query/active-app") as resp:
            text = await resp.text()
            logger.info(f"Active app: {text.strip()}")
            return text

async def launch_app(app_id: str):
    logger.info(f"Launching app {app_id}...")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"http://{TV_IP}:8060/launch/{app_id}") as resp:
            logger.info(f"Launch status: {resp.status}")
    await asyncio.sleep(20)  # Wait for app to load
    await get_active_app()   # Confirm it launched

async def power_on():
    logger.info("Powering ON TV...")
    await send_key("PowerOn")
    await asyncio.sleep(15)  # Wait for TV to boot
    logger.info("TV booted.")

async def power_off():
    logger.info("Powering OFF TV, waiting 15 min...")
    await send_key("PowerOff")
    await asyncio.sleep(OFF_TIME)  # Wait 15 min off
    logger.info("15 min wait complete.")

async def go_home():
    logger.info("Navigating to Home screen...")
    for _ in range(3):
        await send_key("Home")
    await get_active_app()

async def toggle_acr(enable: bool):
    state = "ON" if enable else "OFF"
    logger.info(f"Turning ACR {state}...")
    await go_home()
    await send_key("Up")
    await send_key("Right")
    for _ in range(14):
        await send_key("Down")
    await send_key("Right")
    await send_key("Down")
    await send_key("Down")
    await send_key("Right")
    await send_key("Select")
    await asyncio.sleep(10)
    await send_key("Down")
    await send_key("Select")
    await asyncio.sleep(10)
    if enable:
        await send_key("Down")
        await send_key("Select")
        await asyncio.sleep(10)
    logger.info(f"ACR turned {state}.")


async def watch(source: str, duration: int):
    await get_active_app()
    logger.info(f"Watching {source} for {duration // 60} minutes...")
    await asyncio.sleep(duration)
    logger.info(f"Done watching {source}.")


async def input_text(text: str):
    async with aiohttp.ClientSession() as session:
        for char in text:
            url = f"http://{TV_IP}:8060/keypress/Lit_{char}"
            async with session.post(url) as resp:
                logger.info(f"Typed: {char} | Status: {resp.status}")
            await asyncio.sleep(1)  # Small delay between characters

async def open_antenna_api():
    logger.info("Opening Antenna APP...")
    await send_key("Right")
    await send_key("Down")
    await send_key("Select")
    await asyncio.sleep(15)
    logger.info("Antenna App opened.")

async def open_antenna():
    #Open and watch Antenna Channel
    await open_antenna_api()
    await get_active_app()
    logger.info("Opening Antenna Channel...")
    await asyncio.sleep(5)
    await send_key("Down")
    await send_key("Down")
    await send_key("Left")
    await send_key("Left")
    await send_key("Left")
    await send_key("Down")
    await send_key("Down")
    await send_key("Down")
    await send_key("Right")
    await send_key("Down")
    await send_key("Down")
    await send_key("Select")
    await watch("Antenna Channel", WATCH_TIME)


async def open_fast():
    logger.info("Opening FAST...")
    #Start FAST
    await launch_app(FAST)
    #Go to search
    await send_key("Left")
    await send_key("Up")
    await send_key("Select")
    await asyncio.sleep(3)
    #Get movie
    await input_text("imaginary")
    await asyncio.sleep(3)
    #Go to movie
    for _ in range(0,6):
        await send_key("Right")
    await send_key("Down")
    await send_key("Select")
    await asyncio.sleep(10)
    await send_key("Select")
    await watch("FAST", WATCH_TIME)

async def exit_anything():
    logger.info("Exiting... ")

    for _ in range(0,6):
        await send_key("Back")

async def open_netflix():
    logger.info("Opening Netflix... ")
    await launch_app(NETFLIX)
    for _ in range(0, 4):
        await watch("NETFLIX", NETFLIX_TIME)
        for _ in range(0, 10):
            await send_key("Left")

async def open_youtube():
    #Start Youtube
    logger.info("Opening Youtube... ")
    await launch_app(YOUTUBE)
    await send_key("Select")
    await asyncio.sleep(5)
    await send_key("Back")
    await send_key("Up")
    await send_key("Select")
    await asyncio.sleep(3)
    for _ in range(10):
        await send_key("Right")
    for _ in range(7):
        await send_key("Left")
    await input_text("seksenler 1")
    for _ in range(0,4):
        await send_key("Down")
    for _ in range(0,2):
        await send_key("Right")
    await send_key("Select")
    await send_key("Right")
    await send_key("Select")

    
        
    await watch("YOUTUBE", WATCH_TIME)


async def open_tubi():
    #Start Tubi
    logger.info("Opening Tubi... ")
    await launch_app(TUBI)
    await send_key("Left")
    await send_key("Up")
    await send_key("Select")
    await asyncio.sleep(3)
    await input_text("Jeepers Creepers 2")
    for _ in range(0,7):
        await send_key("Right")
    await send_key("Select")
    await asyncio.sleep(5)
    await send_key("Select")
    await watch("TUBI", WATCH_TIME)

async def open_idle():
    await send_key("Home")
    await send_key("Home")
    await send_key("Home")

    for _ in range (0, 4):
        await watch("IDLE", IDLE_TIME)
        await send_key("Home")

async def open_hdmi():
    await launch_app("tvinput.hdmi2")
    await watch("HDMI", WATCH_TIME)

async def open_antenna_custom():
    await open_antenna_api()
    await send_key("Down")
    await send_key("Down")
    await send_key("Left")
    await send_key("Left")
    await send_key("Left")
    await send_key("Down")
    await send_key("Down")
    await send_key("Down")
    await send_key("Right")
    await send_key("Select")
    await watch("Antenna Custom 10", WATCH_TIME)

async def open_antenna_custom_2():
    await open_antenna_api()
    await send_key("Down")
    await send_key("Down")
    await send_key("Left")
    await send_key("Left")
    await send_key("Left")
    await send_key("Down")
    await send_key("Down")
    await send_key("Down")
    await send_key("Right")
    await send_key("Down")
    await send_key("Select")
    await watch("Antenna Custom 14", WATCH_TIME)
    
   