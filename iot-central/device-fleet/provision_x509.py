import os
import asyncio
import random
import json
import math

from azure.iot.device import X509
from azure.iot.device.aio import ProvisioningDeviceClient
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

DELAY = 2.0
current_period = 0.0

provisioning_host = os.getenv("PROVISIONING_HOST")
id_scope = os.getenv("PROVISIONING_IDSCOPE")
registration_id = os.getenv("DPS_X509_REGISTRATION_ID")
model_id = os.getenv("MODEL_ID")


def stdin_listener():
    """
    Listener for quitting the program
    """
    while True:
        selection = input("Press Q to quit\n")
        if selection == "Q" or selection == "q":
            print("Quitting...")
            break

def get_x509_certificate():
    x509 = X509(
        cert_file=os.getenv("X509_CERT_FILE"),
        key_file=os.getenv("X509_KEY_FILE"),
        pass_phrase=os.getenv("PASS_PHRASE"),
    )
    return x509
    
async def provision_device(provisioning_host, id_scope, registration_id, model_id, x509):
    provisioning_device_client = ProvisioningDeviceClient.create_from_x509_certificate(
            provisioning_host=provisioning_host,
            registration_id=registration_id,
            id_scope=id_scope,
            x509=x509,
        )
        
    provisioning_device_client.provisioning_payload = {"modelId": model_id}
    return await provisioning_device_client.register()

async def send_telemetry(device_client):
    print("Sending telemetry...")
    global current_period

    while True:
        amplitude = 10
        speed = round(amplitude * math.sin(current_period) + random.random() * 2 + 12, 2)
        current_period += math.pi / 8
        
        telemetry = { "Speed": speed }

        msg = Message(json.dumps(telemetry))
        msg.content_encoding = "utf-8"
        msg.content_type = "application/json"
        print(f"Sent message: Speed: {speed:.2f}")
        await device_client.send_message(msg)
        await asyncio.sleep(DELAY)
        
async def main():
    x509 = get_x509_certificate()
    registration_result = await provision_device(provisioning_host, id_scope, registration_id, model_id, x509)

    print("Device provisioning result")
    print(f"Status: {registration_result.status}")

    if registration_result.status == "assigned":
        print(f"Assigned hub: {registration_result.registration_state.assigned_hub}")
        print(f"Device id: {registration_result.registration_state.device_id}")
        
        device_client = IoTHubDeviceClient.create_from_x509_certificate(
            x509=x509,
            hostname=registration_result.registration_state.assigned_hub,
            device_id=registration_result.registration_state.device_id,
        )
    else:
        raise RuntimeError("Could not provision device")

    # Connect the client.
    await device_client.connect()
    
    send_telemetry_task = asyncio.create_task(send_telemetry(device_client))
 
    # Run the stdin listener in the event loop
    loop = asyncio.get_running_loop()
    user_finished = loop.run_in_executor(None, stdin_listener)
   
    # Wait for user to quit the program from the terminal
    await user_finished

    send_telemetry_task.cancel()

    # Shut down the client
    await device_client.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

    # If using Python 3.6 or below, use the following code instead of asyncio.run(main()):
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
    # loop.close()