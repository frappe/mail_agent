import json
from smtp import send_mail


def print_message(channel, method, properties, body) -> None:
    """Prints the message to the console."""

    body = json.loads(body)
    print(f" [x] Received {body}")
    channel.basic_ack(delivery_tag=method.delivery_tag)


def sendmail(channel, method, properties, body) -> None:
    """Sends an email."""

    body = json.loads(body)
    send_mail(body)
    channel.basic_ack(delivery_tag=method.delivery_tag)
