import time
import board
import adafruit_dht
import I2C_LCD_driver

DELAY = 2.0

def main():

    dhtDevice = adafruit_dht.DHT22(board.D4, use_pulseio=False)
    lcd = I2C_LCD_driver.lcd()
    
    print("Measurement started. Press Ctrl-C to exit")
    while True:
        try:
            temperature = dhtDevice.temperature
            humidity = dhtDevice.humidity
            print(f"Temp: {temperature:.1f} C   Humidity: {humidity}% ")

            lcd.lcd_display_string("Temp: {:.1f}{} C".format(temperature, chr(223)), 1)
            lcd.lcd_display_string("Humidity: {:.1f}%".format(humidity), 2)
    
        except KeyboardInterrupt:
            dhtDevice.exit()
            raise SystemExit
        except RuntimeError as error:
            print(error.args[0])
            time.sleep(DELAY)
            continue
    
        time.sleep(DELAY)

if __name__ == '__main__':
    main()
