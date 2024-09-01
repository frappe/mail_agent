import sys
import json
from rabbitmq import RabbitMQ
from utils import get_attr, replace_env_vars


def run(config: dict, queue: str, worker_id: str) -> None:
    """Runs the Mail Agent worker."""

    replace_env_vars(config)

    queues_config = config["queues"]
    rabbitmq_config = config["rabbitmq"]
    rabbitmq = get_rabbitmq_connection(rabbitmq_config)
    declare_queues(rabbitmq, queues_config)
    rabbitmq._disconnect()

    consumer_config = config["consumers"][queue]
    auto_ack = consumer_config["auto_ack"]
    prefetch_count = consumer_config["prefetch_count"]
    callback = get_attr("callback", consumer_config["callback"])
    rabbitmq = get_rabbitmq_connection(rabbitmq_config)
    rabbitmq.consume(queue, callback, auto_ack, prefetch_count)


def get_rabbitmq_connection(rabbitmq_config: dict) -> RabbitMQ:
    """Returns a RabbitMQ connection."""

    return RabbitMQ(
        host=rabbitmq_config["host"],
        port=rabbitmq_config["port"],
        virtual_host=rabbitmq_config["virtual_host"],
        username=rabbitmq_config["username"],
        password=rabbitmq_config["password"],
    )


def declare_queues(rabbitmq: RabbitMQ, queues_config: dict[str, dict]) -> None:
    """Declares the queues in RabbitMQ."""

    for queue, queue_config in queues_config.items():
        rabbitmq.declare_queue(
            queue=queue,
            max_priority=queue_config.get("max_priority", 0),
            durable=queue_config["durable"],
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        queue = sys.argv[1]
        worker_id = sys.argv[2]

        with open("config.json") as config_file:
            config = json.load(config_file)

        run(config, queue, worker_id)
    else:
        print("Please setup the Mail Agent by running the `mail-agent setup`.")
