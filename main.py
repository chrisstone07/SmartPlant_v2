import os
import sys
import Adafruit_DHT
from gpiozero import LED, Button, DistanceSensor
from time import sleep
import time
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials

import pubnub
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
from pubnub.callbacks import SubscribeCallback
from pubnub.enums import PNOperationType, PNStatusCategory
import config
 
pnconfig = PNConfiguration()
pnconfig.subscribe_key = config.subscribe_key
pnconfig.publish_key = config.publish_key
pnconfig.ssl = False

# json_key = json.load(open('creds.json')) # json credentials you downloaded earlier
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
 
pubnub = PubNub(pnconfig)

oldtime = time.time()

#Pump & BorePump is connected to GPIO4, GPIO11 as an LED
pump = LED(4)
borepump = LED(11)

#DHT Sensor is connected to GPIO17
sensortype = 11
pin = 17

#Soil Moisture sensor and Rain Sensor is connected to GPIO14, GPIO13 as a button
soil = Button(14)
rain = Button(13)

flag = 1

ECHO = 9
TRIG = 10
sensor = DistanceSensor(echo=ECHO, trigger=TRIG, max_distance=0.5)

borepump.off()
# pump.on()

gfile = gspread.authorize(credentials) # authenticate with Google
sheet = gfile.open("Smart_Irrigation_System").sheet1 # open sheet

class MySubscribeCallback(SubscribeCallback):
    def status(self, pubnub, status):
        pass
        # The status object returned is always related to subscribe but could contain
        # information about subscribe, heartbeat, or errors
        # use the operationType to switch on different options
        if status.operation == PNOperationType.PNSubscribeOperation \
                or status.operation == PNOperationType.PNUnsubscribeOperation:
            if status.category == PNStatusCategory.PNConnectedCategory:
                pass
                # This is expected for a subscribe, this means there is no error or issue whatsoever
            elif status.category == PNStatusCategory.PNReconnectedCategory:
                pass
                # This usually occurs if subscribe temporarily fails but reconnects. This means
                # there was an error but there is no longer any issue
            elif status.category == PNStatusCategory.PNDisconnectedCategory:
                pass
                # This is the expected category for an unsubscribe. This means there
                # was no error in unsubscribing from everything
            elif status.category == PNStatusCategory.PNUnexpectedDisconnectCategory:
                pass
                # This is usually an issue with the internet connection, this is an error, handle
                # appropriately retry will be called automatically
            elif status.category == PNStatusCategory.PNAccessDeniedCategory:
                pass
                # This means that PAM does allow this client to subscribe to this
                # channel and channel group configuration. This is another explicit error
            else:
                pass
                # This is usually an issue with the internet connection, this is an error, handle appropriately
                # retry will be called automatically
        elif status.operation == PNOperationType.PNSubscribeOperation:
            # Heartbeat operations can in fact have errors, so it is important to check first for an error.
            # For more information on how to configure heartbeat notifications through the status
            # PNObjectEventListener callback, consult <link to the PNCONFIGURATION heartbeart config>
            if status.is_error():
                pass
                # There was an error with the heartbeat operation, handle here
            else:
                pass
                # Heartbeat operation was successful
        else:
            pass
            # Encountered unknown status type
 
    def presence(self, pubnub, presence):
        pass  # handle incoming presence data
 
    def message(self, pubnub, message):
        if message.message == 'ON':
            global flag
            flag = 1
        elif message.message == 'OFF':
            global flag
            flag = 0
        elif message.message == 'WATER':
            pump.off()
            sleep(5)
            pump.on()
 
 
pubnub.add_listener(MySubscribeCallback())
pubnub.subscribe().channels('ch1').execute()

def distance():
    distance = sensor.distance * 100
    return distance

def publish_callback(result, status):
        pass

def get_status_soil():
        if soil.is_held:
                print("wet")
                return True
        else:
                print("dry")
                return False

def get_status_rain():
    if rain.is_held:
        print("Raining")
        return True
    else:
        print("Not Raining")
        return False

def send_data(dataa):
    sheet.append_row(dataa)

while True:
    try:
        if flag ==1:
            # Try to grab a sensor reading.  Use the read_retry method which will retry up
            # to 15 times to get a sensor reading (waiting 2 seconds between each retry).
            humidity, temperature = Adafruit_DHT.read_retry(sensortype, pin)

            # dictionary = {"eon": {"Temperature": temperature, "Humidity": humidity}}

            wet = get_status_soil()
            raining = get_status_rain()		

            if wet == False:
                print("turning waterpump on")
                motorstat = "ON"
                pump.on()
                moiststat = "Dry"
                sleep(1)
            else:
                pump.off()
                motorstat = "OFF"
                moiststat = "Wet"

            if raining == True:
                rain_stat = "Raining"
            else:
                rain_stat = "Not Raining"
            
            dist = 50 - distance()

            if dist > 40:
                watlevel = 50
                watlevelwords = "HIGH"
                borepump.off()
            elif dist > 10 and dist < 40:
                watlevel = 25
                watlevelwords = "MEDIUM"
                borepump.off()
            else:
                watlevel = 0
                watlevelwords = "LOW"
                print("Turning Bore pump on")
                borepump.on()

            DHT_Read = ('Temp={0:0.1f}*  Humidity={1:0.1f}% RainStatus={2} MotorStatus={3} WaterLevel={4}'.format(temperature, humidity, rain_stat, motorstat, watlevelwords))
            print(DHT_Read)

            dictionary = {"eon": {"Temperature": temperature, "Humidity": humidity, "WaterLevel": watlevel}}

            pubnub.publish().channel('ch2').message([DHT_Read]).pn_async(publish_callback)
            pubnub.publish().channel("eon-chart").message(dictionary).pn_async(publish_callback)

            current_time = time.time()

            if current_time - oldtime > 10: # in seconds
                oldtime = current_time
                send_data([datetime.datetime.now().strftime("%Y/%m/%d %I:%M:%S %p"), temperature, humidity, watlevelwords, moiststat, rain_stat, motorstat])
            sleep(1)

        elif flag == 0:
            pump.on()
            sleep(3)

    except KeyboardInterrupt:
        sys.exit()
        os._exit()    
    # elif flag == 0:
        # 	pump.on()
        # 	sleep(3)
