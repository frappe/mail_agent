import pika


class RabbitMQ:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.__host = host
        self.__port = port
        self.__username = username
        self.__password = password
        self._connection = None
        self._channel = None
        self._connect()

    def _connect(self) -> None:
        if self.__username and self.__password:
            credentials = pika.PlainCredentials(self.__username, self.__password)
            parameters = pika.ConnectionParameters(
                host=self.__host, port=self.__port, credentials=credentials
            )
        else:
            parameters = pika.ConnectionParameters(host=self.__host, port=self.__port)

        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

    def declare_queue(self, queue: str, durable: bool = True) -> None:
        self._channel.queue_declare(queue=queue, durable=durable)

    def consume(self, queue: str, callback: callable, auto_ack: bool = False) -> None:
        self._channel.basic_consume(
            queue=queue, on_message_callback=callback, auto_ack=auto_ack
        )
        self._channel.start_consuming()

    def _disconnect(self) -> None:
        if self._connection and self._connection.is_open:
            self._connection.close()

    def __del__(self) -> None:
        self._disconnect()
