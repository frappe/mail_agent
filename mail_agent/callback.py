import json


def print_message(channel, method, properties, body):
    body = json.loads(body)
    print(f" [x] Received {body}")
    channel.basic_ack(delivery_tag=method.delivery_tag)
