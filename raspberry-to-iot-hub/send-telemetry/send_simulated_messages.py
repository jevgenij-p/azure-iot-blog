import asyncio
import random
from azure.iot.device import Message
from azure.iot.device.aio import IoTHubDeviceClient

CONNECTION_STRING = ""

TEMPERATURE = 20.0
HUMIDITY = 60
PAYLOAD = '{{"temperature": {temperature}, "humidity": {humidity}}}'

async def main():

    try:
        # Create instance of the device client
        client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

        print("Simulated device started. Press Ctrl-C to exit")
        while True:

            temperature = round(TEMPERATURE + (random.random() * 15), 2)
            humidity = round(HUMIDITY + (random.random() * 20), 2)
            data = PAYLOAD.format(temperature=temperature, humidity=humidity)
            message = Message(data)

            # Send a message to the IoT hub
            print(f"Sending message: {message}")
            await client.send_message(message)
            print("Message successfully sent")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("Simulated device stopped")

if __name__ == '__main__':
    asyncio.run(main())
