import os
import asyncio
import random
import logging
import json
import board
import adafruit_dht
import I2C_LCD_driver

from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device.aio import ProvisioningDeviceClient
from azure.iot.device import constant, Message, MethodResponse
from datetime import date, timedelta, datetime

logging.basicConfig(level=logging.ERROR)

DELAY = 5.0
DEFAULT_OPTIMAL_TEMPERATURE = 25.0

optimal_temperature = DEFAULT_OPTIMAL_TEMPERATURE

provisioning_host = os.getenv("PROVISIONING_HOST")
id_scope = os.getenv("ID_SCOPE")
registration_id = os.getenv("DEVICE_ID")
symmetric_key = os.getenv("DEVICE_KEY")

def stdin_listener():
    """
    Listener for quitting the program
    """
    while True:
        selection = input("Press Q to quit\n")
        if selection == "Q" or selection == "q":
            print("Quitting...")
            break

async def provision_device(provisioning_host, id_scope, registration_id, symmetric_key):
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=id_scope,
        symmetric_key=symmetric_key)
    return await provisioning_device_client.register()

async def send_telemetry(device_client, lcd, dhtDevice):
    print("Sending telemetry...")

    while True:
        try:
            # Read sensor data
            temperature = dhtDevice.temperature
            humidity = dhtDevice.humidity

            telemetry = { "Temperature": temperature, "Humidity": humidity }
            msg = Message(json.dumps(telemetry))
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"
            print(f"Sent message: Temperature: {temperature:.1f} C  Humidity {humidity}% ")

            lcd.lcd_display_string(f"{temperature:.1f}{chr(223)}C   {humidity:.1f}%", 1)

        except RuntimeError as error:
            print(error.args[0])
            await asyncio.sleep(1)
            continue

        await device_client.send_message(msg)
        await asyncio.sleep(DELAY)

async def execute_command_listener(
    device_client, lcd, method_name, user_command_handler, create_user_response_handler):

    while True:
        command_name = method_name if method_name else None

        command_request = await device_client.receive_method_request(command_name)
        print("Command request received with payload")

        values = {}
        if not command_request.payload:
            print("Payload was empty.")
        else:
            print(f"Payload: {command_request.payload}")
            values = command_request.payload

        await user_command_handler(values, lcd)

        response_status = 200
        response_payload = create_user_response_handler(values)

        command_response = MethodResponse.create_from_method_request(
            command_request, response_status, response_payload)

        try:
            await device_client.send_method_response(command_response)
        except Exception:
            print(f"Responding to the {method_name} command failed")

async def receive_desired_properties_patch(device_client):
    patch = await device_client.receive_twin_desired_properties_patch()  # blocking call
    print(f"Desired properties patch: {patch}")
    
    version = patch["$version"]
    prop_dict = {}

    ignore_keys = ["__t", "$version"]
    for prop_name, prop_value in patch.items():
        if prop_name in ignore_keys:
            continue
        prop_dict[prop_name] = {
            "ac": 200,
            "ad": "Successfully executed patch",
            "av": version,
            "value": prop_value,
        }

    await device_client.patch_twin_reported_properties(prop_dict)
    return patch

async def execute_property_listener(device_client, lcd):
    global optimal_temperature

    while True:
        patch = await receive_desired_properties_patch(device_client)

        if "OptimalTemperature" in patch.keys():
            optimal_temperature = patch["OptimalTemperature"]
            lcd.lcd_display_string(f"Desired: {optimal_temperature:.1f}{chr(223)}C", 2)
            print(f"Desired OptimalTemperature property: {optimal_temperature}")

async def reset_handler(values, lcd):
    print("Reset command received")
    lcd.lcd_clear()
    lcd.lcd_display_string(f"Cmd: Reset({values})", 2)

def create_reset_response(values):
    response = {"result": True, "data": "reset succeeded"}
    return response

async def read_desired_properties(device_client, lcd):
    global optimal_temperature

    twin = await device_client.get_twin()
    if "desired" in twin.keys():
        desired = twin["desired"]
        if "OptimalTemperature" in desired.keys():
            optimal_temperature = desired["OptimalTemperature"]
            lcd.lcd_display_string(f"Desired: {optimal_temperature:.1f}{chr(223)}C", 2)
            print(f"Desired OptimalTemperature property: {optimal_temperature}")


async def main():

    registration_result = await provision_device(
            provisioning_host, id_scope, registration_id, symmetric_key)

    if registration_result.status == "assigned":
        print("Device was assigned")
        print(f"Assigned Hub: {registration_result.registration_state.assigned_hub}")
        print(f"Device id: {registration_result.registration_state.device_id}")

        device_client = IoTHubDeviceClient.create_from_symmetric_key(
            symmetric_key=symmetric_key,
            hostname=registration_result.registration_state.assigned_hub,
            device_id=registration_result.registration_state.device_id)
    else:
        raise RuntimeError("Could not provision device. Aborting Plug and Play device connection.")

    # Initialize temperature sensor
    dhtDevice = adafruit_dht.DHT22(board.D4, use_pulseio=False)

    # Initialize LCD display driver
    lcd = I2C_LCD_driver.lcd()

    # Connect the iot device client
    await device_client.connect()

    await read_desired_properties(device_client, lcd)

    # Set OptimalTemperature property
    await device_client.patch_twin_reported_properties({"OptimalTemperature": optimal_temperature})

    listeners = asyncio.gather(
        execute_command_listener(
            device_client,
            lcd,
            method_name="Reset",
            user_command_handler=reset_handler,
            create_user_response_handler=create_reset_response,
        ),
        execute_property_listener(device_client, lcd),
    )

    send_telemetry_task = asyncio.create_task(send_telemetry(device_client, lcd, dhtDevice))
 
    # Run the stdin listener in the event loop
    loop = asyncio.get_running_loop()
    user_finished = loop.run_in_executor(None, stdin_listener)
   
    # Wait for user to quit the program from the terminal
    await user_finished

    if not listeners.done():
        listeners.set_result("DONE")

    listeners.cancel()
    send_telemetry_task.cancel()
    dhtDevice.exit()

    # Shut down the client
    await device_client.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
