import json
from mail_agent import app


# TODO: Remove
def callback(channel, method, properties, body):
    body = json.loads(body)
    print(f" [x] Received {body}")
    channel.basic_ack(delivery_tag=method.delivery_tag)


config = {
    # TODO: Use Environment Variables
    "rabbitmq": {"host": "localhost", "port": 5672, "username": None, "password": None},
    "queues": {
        "mail::outgoing_mail": {"durable": True},
        "mail::outgoing_mails": {"durable": True},
    },
    "consumers": {
        "mail::outgoing_mail": {"callback": callback, "auto_ack": False, "workers": 3},
        "mail::outgoing_mails": {"callback": callback, "auto_ack": False, "workers": 5},
    },
}


if __name__ == "__main__":
    app.run(config)
