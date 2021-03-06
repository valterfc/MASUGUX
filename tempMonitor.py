import time

from umqtt.simple import MQTTClient

from machine import Pin
from machine import reset

import network

from os import listdir
from os import remove


# Publish test messages e.g. with:
# mosquitto_pub -t foo_topic -m hello

class freezer:
    def __init__(self, bb_mqtt_id="None", mqtt_broker="None", mqtt_port=0, mqtt_user="None", mqtt_passwd="None",
                 topic="None"):
        self.relay_one = Pin(12, Pin.OUT)
        self.relay_two = Pin(13, Pin.OUT)

        self.bb_mqtt_id = "ElectroDragon"
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_passwd = mqtt_passwd
        self.topic = topic
        self.mqtt = MQTTClient(self.bb_mqtt_id, self.mqtt_broker, self.mqtt_port, self.mqtt_user, self.mqtt_passwd)
        self.sta_if = network.WLAN(network.STA_IF)

        self.programs = {'fermentation': [18.0, 22.0], 'maturation': [0.0, 2.0], 'priming': [20.0, 23.0]}

        self.style = 'fermentation'
        self.programLoad()

        self.MINIMUM = self.programs[self.style][0]
        self.MAXIMUM = self.programs[self.style][1]

        self.relay_status = "OFF"

        print("Waiting IP...")
        size = 0
        while size < 11:
            try:
                size = len(self.sta_if.ifconfig()[0])
                time.sleep_ms(80)
            except:
                size = 0

        self.mqtt.connect()

    def programLoad(self):
        prog = listdir(".")
        if not "program.ini" in prog:
            print("Arquivo de programa nao existe")
        else:
            f = open("program.ini","r")
            self.style = f.read()
            f.close()

            self.MINIMUM = self.programs[self.style][0]
            self.MAXIMUM = self.programs[self.style][1]

            print("Programa carregado:")
            print(self.style)
            print("Minima:")
            print(self.MINIMUM)
            print("Maxima:")
            print(self.MAXIMUM)

    def defineProgram(self,programTo):
        progFile = listdir(".")
        if "program.ini" in progFile:
            remove("program.ini")

        f = open("program.ini","w")

        if type(programTo) is bytes:
            value = programTo.decode()
        else:
            value = programTo

        f.write(value)
        f.close()

        self.programLoad()

    def ts2name(self):
        val = str(time.localtime())
        return val

    def log(self, msg):
        f = open("tempMonitor.log", 'a')
        message = self.ts2name()
        messages = message + msg
        f.write(messages)
        f.close()

        reset()

    def doSleep(self):
        try:
            #diz ao esp monitor para dormir, apos ter recebido a mensagem
            # self.mqtt.connect()
            self.mqtt.publish(b"freezer/sleep", b'1')
        except:
            print("Nao foi possivel conectar ao broker")
            self.log("Nao foi possivel fazer publish\r\n ")

    def toNumber(self, target):
        try:
            if len(target) == 4:
                temp = (target[0] - 48) * 10.0
                temp += (target[1] - 48) * 1.0
                temp += (target[3] - 48) * 0.1

            elif len(target) == 3:
                if not target.find(b'.') == 1:
                    return 0.0

                temp = (target[0] - 48) * 1.0
                temp += (target[2] - 48) * 0.1

        except:
            self.log("Falha no calculo da temperatura")

        self.doSleep()
        return temp

    # Received messages from subscriptions will be delivered to this callback
    def sub_cb(self, topic, msg):
        print((topic, msg))
        print("temperaturas do programa atual:")
        print(self.MINIMUM)
        print(self.MAXIMUM)

        try:
            if topic == b'beer/program':
                if msg.decode() in self.programs.keys():
                    self.defineProgram(msg)
                    #self.MINIMUM = self.programs[msg][0]
                    #self.MAXIMUM = self.programs[msg][1]
                    #print("Programa escolhido:")
                    #print(msg)

            elif topic == b'beer/temperature':
                temp = self.toNumber(msg)
                if temp > self.MAXIMUM:
                    self.relay_one.high()
                    print("relay ON")
                    self.relay_status = "ON"

                elif temp < self.MINIMUM:
                    self.relay_one.low()
                    print("relay OFF")
                    self.relay_status = "OFF"

            self.mqtt.publish(b"freezer/relay", self.relay_status)

        except:
            self.log("Falha no callback\r\n ")

    def check(self, server="192.168.1.2"):
        print("Connecting...")
        print("Setting callback...")
        try:
            self.mqtt.set_callback(self.sub_cb)
        except:
            self.log("Falha em set_callback")

        # self.mqtt.connect()
        print("Subscribe to beer/temperature...")
        self.mqtt.subscribe(b"beer/#")
        while True:
            try:
                if True:
                    # Blocking wait for message
                    self.mqtt.wait_msg()
                else:
                    # Non-blocking wait for message
                    self.mqtt.check_msg()
                    # Then need to sleep to avoid 100% CPU usage (in a real
                    # app other useful actions would be performed instead)
                    time.sleep_ms(1)
            except:
                self.log("Falha no mqtt.wait_msg ou mqtt.check_msg\r\n ")
            time.sleep_ms(1)

        self.mqtt.disconnect()
