import json
import time
import uuid
import pika
import random

from multiprocessing import Process


class Node:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.nodes = {self.id}
        print(self.id)

        self.connections = {}
        self.channels = {}

        # entrance queue ########
        self.connections['entrance'] = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channels['entrance'] = self.connections['entrance'].channel()
        result = self.channels['entrance'].queue_declare(queue='', durable=True) # self queue
        queue = result.method.queue
        self.channels['entrance'].exchange_declare(exchange='entrance', exchange_type='fanout', auto_delete=False)
        self.channels['entrance'].queue_bind(exchange='entrance', queue=queue) # broker subscribe
        self.channels['entrance'].basic_consume(on_message_callback=self.callback_entrance, queue=queue)
        self.join()
        self.channels['entrance'].start_consuming()
        
        # election queue ########
        self.connections['election'] = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channels['election'] = self.connections['election'].channel()
        result = self.channels['election'].queue_declare(queue='', durable=True) # self queue
        queue = result.method.queue
        self.channels['election'].exchange_declare(exchange='election', exchange_type='fanout', auto_delete=False)
        self.channels['election'].queue_bind(exchange='election', queue=queue) # broker subscribe
        self.channels['election'].basic_consume(on_message_callback=self.callback_election, queue=queue)
        self.channels['election'].start_consuming()


    def join(self):
        data = {'id': self.id }
        self.channels['entrance'].basic_publish(exchange='entrance', routing_key='', body=json.dumps(data), 
                                                properties=pika.BasicProperties(delivery_mode=2)) # make message persistent
        # criar um daemon pra ficar mandando


    def callback_entrance(self, ch, method, properties, body):
        r = json.loads(body.decode("utf-8"))

        if r['id'] not in self.nodes:
            self.nodes.add(r['id'])
            print(f"{r['id']} inside chain! {len(self.nodes)} participants.")

        if id != r['id']:
            self.channels['entrance'].basic_publish(exchange='entrance', routing_key='', body=body)


    def callback_election(self, ch, method, properties, body):
        return