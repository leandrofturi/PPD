import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()

channel.queue_declare(queue="rsv/hello")

channel.basic_publish(exchange="", routing_key="rsv/hello", body="Hello World #2!")
print("Sent 'Hello World #2!'")
connection.close()
