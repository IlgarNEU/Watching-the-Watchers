import asyncio
from aiowebostv import WebOsClient
import wakeonlan


TV_IP = "192.168.14.119"
TV_MAC = "00:A1:59:8F:AB:38"
CLIENT_KEY = "e71f8a7795d3c9229b5ce3a57270332f"

async def get_client_key():
    # 1. Create client with just the TV's IP (no key yet)
    client = WebOsClient(TV_IP)
    
    # 2. Connect — this will prompt the TV to show a pairing request
    await client.connect()
    
    # 3. After the user accepts the prompt on the TV,
    #    the client key is available here:
    print("Client Key:", client.client_key)
    
    await client.disconnect()

asyncio.run(get_client_key())

"""
def wake_tv():
    wakeonlan.send_magic_packet(TV_MAC)

async def connect(retries=10):
    for attempt in range(retries):
        try:
            #logger.info(f"Connecting (attempt {attempt+1}/{retries})...")
            client = WebOsClient(TV_IP, client_key=CLIENT_KEY)
            await client.connect()
            #logger.info("Connected!")
            return client
        except Exception as e:
            print("Warning")
            #logger.warning(f"Connection failed: {e}")
            await asyncio.sleep(20)
    raise Exception("Could not connect after all retries.")

async def power_on():
    #logger.info("Sending Wake-on-LAN...")
    wake_tv()
    await asyncio.sleep(20)  # Wait for TV to boot
    client = await connect()  # Connect after boot
    return client

async def power_off(client):
    #logger.info("Powering off TV...")
    await client.power_off()
    await asyncio.sleep(300)  # Wait before reconnecting

async def main():
    # Power on via WoL
    client = await power_on()

    # Do your stuff
    await client.button("HOME")
    await asyncio.sleep(3)
    await client.button("HOME")
    await asyncio.sleep(3)
    await client.button("HOME")
    await asyncio.sleep(3)


    # Power off
    #await power_off(client)

    # Power on again
    #client = await power_on()

asyncio.run(main())

async def main():
    client = WebOsClient(TV_IP, client_key=CLIENT_KEY)
    await client.connect()
    
    methods = [m for m in dir(client) if not m.startswith("_")]
    for m in methods:
        print(m)

    #await client.power_on()
    #await client.button("DOWN")
    




asyncio.run(main())
"""