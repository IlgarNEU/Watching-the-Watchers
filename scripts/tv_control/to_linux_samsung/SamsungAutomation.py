#TODO: Fix Timings
#TODO: Fix IP address and MAC

#DONE (remember for other tvs):
#TODO: Channel fix after custom for later experiments for normal channel and wiseworse
#TODO: Fix any problem with Youtube search
#TODO: Fix any problem with Tubi search 
#TODO: App Exits
#TODO: Check if FAST is really FAST



from samsungtvws import SamsungTVWS
from wakeonlan import send_magic_packet
import logging
from datetime import datetime
import asyncio


OFF_TIME = 120       #The duration TV stays OFF
BOOT_TIME = 15      #The duration needed after turning on
WATCH_TIME = 900     #The duration needed to watch each scenario
IDLE_TIME = 225      #The duration needed to stay IDLE and repeat N times
NETFLIX_TIME = 225   #The duration needed to wait until trailer ends and go back N times

TV_IP = "192.168.14.118"       #TV IP
TV_MAC = "04:E4:B6:74:DD:94"  #TV MAC
TV_BROADCAST = "192.168.14.255"

NETFLIX = "3201907018807"     #NETFLIX APP ID
YOUTUBE = "111299001912"      #YOUTUBE APP ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"samsung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def connect(retries=10):
    for attempt in range(retries):
        try:
            logger.info(f"Connecting (attempt {attempt+1}/{retries})...")
            tv = SamsungTVWS(
                host=TV_IP,
                port=8002,
                token_file="tv_token.txt",
                timeout=10
            )
            # Force connection open immediately by sending a no-op
            tv.send_key("KEY_NULL")
            logger.info("Connected to TV.")
            return tv
        except Exception as e:
            logger.warning(f"Connection attempt {attempt+1} failed: {e}")
            await asyncio.sleep(10)
            send_magic_packet(TV_MAC, ip_address=TV_BROADCAST)
            await asyncio.sleep(20)
    raise Exception("Could not connect after all retries.")

def is_tv_reachable(tv):
    try:
        tv.rest_device_info()
        return True
    except Exception:
        return False

def is_tv_on(tv):
    try:
        info = tv.rest_device_info()
        return info.get("device", {}).get("PowerState") == "on"
    except Exception as e:
        logger.warning(f"WARNING: Could not get TV power state: {e}")
        return False

async def power_on(tv):
    if is_tv_on(tv):
        logger.info("TV is already on.")
        return

    if is_tv_reachable(tv):
        # TV is reachable but off (standby) — KEY_POWER will work
        logger.info("TV is in standby, turning on via KEY_POWER...")
        tv.send_key("KEY_POWER")
    else:
        # TV is fully off/unreachable — need WoL
        logger.info("TV is unreachable, sending Wake-on-LAN...")
        send_magic_packet(TV_MAC, ip_address=TV_BROADCAST)
    await asyncio.sleep(BOOT_TIME)                                  #BOOT_TIME delay to let TV boot

    if is_tv_on(tv):
        logger.info("TV is now on.")
    else:
        logger.warning("WARNING: TV did not turn on successfully.")


async def power_off(tv):
    if is_tv_on(tv):
        logger.info("Turning TV off...")
        tv.send_key("KEY_POWER")
        await asyncio.sleep(OFF_TIME)                               #TIME TV STAYS OFF
    else:
        logger.info("TV is already off.")

async def go_home(tv):
    logger.info("Going home...")
    for _ in range(3):
        tv.send_key("KEY_HOME")
        await asyncio.sleep(2)                                      #TIME TO WAIT AFTER HOME BUTTON X 3


async def key_left(tv):
    logger.info("Press Left key... ")
    tv.send_key("KEY_LEFT")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS


async def key_right(tv):
    logger.info("Press Right key... ")
    tv.send_key("KEY_RIGHT")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS


async def key_down(tv):
    logger.info("Press Down key... ")
    tv.send_key("KEY_DOWN")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS


async def key_up(tv):
    logger.info("Press Up key... ")
    tv.send_key("KEY_UP")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS


async def key_enter(tv):
    logger.info("Press Enter key... ")
    tv.send_key("KEY_ENTER")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS

async def key_return(tv):
    logger.info("Press return key... ")
    tv.send_key("KEY_RETURN")
    await asyncio.sleep(2)                                          #WAIT AFTER THE BUTTON PRESS

async def open_netflix(tv):
    logger.info("Opening Netflix...")
    tv.rest_app_run(NETFLIX)
    await asyncio.sleep(20)                                          #WAIT TO LAUNCH THE APP
    for _ in range(0, 4):
        await asyncio.sleep(NETFLIX_TIME)
        tv = await connect()
        for _ in range(0, 13):
            await key_left(tv)



async def open_youtube(tv):
    logger.info("Opening YouTube...")
    tv.rest_app_run(YOUTUBE)
    await asyncio.sleep(20)
    tv = await connect()
    #Going to search 
    await key_enter(tv)
    await key_up(tv)
    await key_right(tv)
    await key_enter(tv)

    #Select the last watched film
    await key_left(tv)
    await key_enter(tv)
    await asyncio.sleep(3)

    #Select the film after search
    await key_right(tv)
    await key_enter(tv)
    await asyncio.sleep(WATCH_TIME)



async def open_tubi(tv):
    logger.info("Opening Tubi...")

    #Open Tubi through navigation
    for _ in range(0, 2):
        await key_right(tv)

    await key_down(tv)

    for _ in range(0, 13):
        await key_right(tv)
    
    await key_enter(tv)

    #WAIT APP TO LAUNCH
    await asyncio.sleep(20)
    tv = await connect()
    #Go to search
    await key_left(tv)
    await key_up(tv)
    await key_enter(tv)

    #Search movie
    #tv.send_text("Jeepers Creepers 2")

    #Go to movie
    for _ in range(0, 7):
        await key_right(tv)

    #Select movie
    await key_enter(tv)
    await asyncio.sleep(3)

    #Start movie and watch
    await key_enter(tv)
    await asyncio.sleep(WATCH_TIME)


async def open_hdmi(tv):
    logger.info("Opening HDMI...")
    await key_left(tv)
    await key_down(tv)
    for _ in range(0, 3):
        await key_right(tv)
    await key_enter(tv)
    await asyncio.sleep(WATCH_TIME)
    
async def toggle_acr(tv):
    logger.info("Toggling ACR...")
    await key_left(tv)
    for _ in range(0, 2):
        await key_down(tv)
    for _ in range(0, 2):
        await key_enter(tv)
        await asyncio.sleep(3)

    for _ in range(0, 4):
        await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(3)

    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(3)

    for _ in range(0, 3):
        await key_down(tv)
    for _ in range(0, 2):
        await key_enter(tv)
        await asyncio.sleep(10)

    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(3)

    await key_down(tv)
    for _ in range(0, 2):
        await key_enter(tv)
        await asyncio.sleep(10)

    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(3)



async def open_fast(tv):
    logger.info("Opening FAST")
    await key_down(tv)
    await key_down(tv)
    await key_right(tv)
    await key_enter(tv)
    logger.info("Watching FAST")
    await asyncio.sleep(WATCH_TIME)
    
async def open_antenna(tv):
    logger.info("Opening Antenna Channel")
    await key_down(tv)
    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(WATCH_TIME)

async def open_antenna_custom(tv):
    logger.info("Opening Antenna Custom (10.1)")
    await key_down(tv)
    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(20)
    tv = await connect()
    await asyncio.sleep(2)
    tv.send_key("KEY_CHDOWN")
    await asyncio.sleep(2)
    tv.send_key("KEY_CHDOWN")
    await asyncio.sleep(WATCH_TIME)
    tv = await connect()
    tv.send_key("KEY_CHUP")
    await asyncio.sleep(2)
    tv.send_key("KEY_CHUP")
    await asyncio.sleep(2)


async def open_antenna_custom_2(tv):
    logger.info("Opening Antenna Custom 14.1")
    await key_down(tv)
    await key_down(tv)
    await key_enter(tv)
    await asyncio.sleep(20)
    tv = await connect()
    await asyncio.sleep(2)
    tv.send_key("KEY_CHDOWN")
    await asyncio.sleep(WATCH_TIME)
    tv = await connect()
    tv.send_key("KEY_CHUP")
    await asyncio.sleep(2)





async def open_idle(tv):
    logger.info("Opening IDLE")
    await go_home(tv)
    await key_right(tv)
    await key_right(tv)
    for _ in range(4): 
        await asyncio.sleep(IDLE_TIME)
        tv = await connect()
        await go_home(tv)
        await key_right(tv)
        await key_right(tv)

async def exit_fast_antenna(tv):
    logger.info("Exiting")
    await go_home(tv)

async def exit_netflix(tv):
    logger.info("Exiting")
    for _ in range(0, 3):
        await key_return(tv)


async def exit_youtube(tv):
    logger.info("Exiting")
    for _ in range(0, 6):
        await key_return(tv)
    

async def exit_tubi(tv):
    logger.info("Exiting")
    for _ in range(0, 8):
        await key_return(tv)



async def run():

    tv = await connect()
    """
    methods = [m for m in dir(tv) if not m.startswith("_")]
    for m in methods:
        print(m)
    """
    
    await open_antenna_custom(tv)

    