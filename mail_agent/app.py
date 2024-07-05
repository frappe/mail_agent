import sys
from typing import Any
from multiprocessing import Process
from mail_agent.haraka import Haraka
from mail_agent.utils import get_attr
from mail_agent.rabbitmq import RabbitMQ


def run(config: dict[str, Any]):
    start()
    queues_config: dict[str, dict] = config["queues"]
    haraka_config: dict[str, Any] = config["haraka"]
    rabbitmq_config: dict[str, Any] = config["rabbitmq"]
    consumers_config: dict[str, dict] = config["consumers"]

    haraka = Haraka()
    haraka.setup(haraka_config)

    rabbitmq = get_rabbitmq_connection(rabbitmq_config)
    declare_queues(rabbitmq, queues_config)
    rabbitmq._disconnect()

    processes = []
    for queue, consumer_config in consumers_config.items():
        callback = get_attr("mail_agent.callback", consumer_config["callback"])
        auto_ack = consumer_config["auto_ack"]
        workers = consumer_config["workers"]

        for worker in range(1, workers + 1):
            process = Process(
                target=create_consumer,
                name=f"consumer-{queue}-{worker}",
                args=(worker, rabbitmq_config, queue, callback, auto_ack),
            )
            process.start()
            processes.append(process)

    for process in processes:
        process.join()


def start():
    print("\n[X] Starting Mail Agent ...")


def get_rabbitmq_connection(rabbitmq_config: dict) -> RabbitMQ:
    try:
        rabbitmq = RabbitMQ(
            host=rabbitmq_config["host"],
            port=rabbitmq_config["port"],
            username=rabbitmq_config["username"],
            password=rabbitmq_config["password"],
        )
    except Exception as e:
        print(f"Error connecting to RabbitMQ: {e}")
        sys.exit(1)

    return rabbitmq


def declare_queues(rabbitmq: RabbitMQ, queues_config: dict[str, dict]) -> None:
    for queue, queue_config in queues_config.items():
        try:
            rabbitmq.declare_queue(queue=queue, durable=queue_config["durable"])
            print(f"[X] Queue {queue} declared")
        except Exception as e:
            print(f"Error declaring queue {queue}: {e}")
            sys.exit(1)


def create_consumer(
    worker_count: int,
    rabbitmq_config: dict,
    queue: str,
    callback: callable,
    auto_ack: bool,
) -> None:
    print(f"[X] Starting consumer {worker_count} for queue {queue}")
    rabbitmq = get_rabbitmq_connection(rabbitmq_config)
    rabbitmq.consume(queue, callback, auto_ack)
