import paho.mqtt.client as mqtt
from random import randrange, uniform
import time

mqttBroker = "127.0.0.1"
mqttBroker = "broker.emqx.io"

client = mqtt.Client("Node_2")
client.connect(mqttBroker)

while True:
    randNumber = randrange(15, 25)
    client.publish("rsv/temp", randNumber)
    print("Just published " + str(randNumber) + " to topic rsv/temp")
    time.sleep(1)
