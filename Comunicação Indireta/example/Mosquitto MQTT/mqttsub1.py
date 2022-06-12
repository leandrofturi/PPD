import paho.mqtt.client as mqtt
import time


def on_message(client, userdata, message):
    print("received message: ", str(message.payload.decode("utf-8")))


mqttBroker = "127.0.0.1"
mqttBroker = "broker.emqx.io"

client = mqtt.Client("Node_3")
client.connect(mqttBroker)

client.loop_start()

client.subscribe("rsv/temp")
client.subscribe("rsv/light")
client.on_message = on_message

time.sleep(30000)
client.loop_stop()
