import os
from queue import Queue
from email import policy
from smtplib import SMTP
from threading import Lock
from email.parser import Parser


class SMTPConnectionPool:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 25,
        username: str | None = None,
        password: str | None = None,
        pool_size: int = 5,
    ) -> None:
        self.__host = host
        self.__port = port
        self.__username = username
        self.__password = password
        self.__lock = Lock()
        self.__current_pool_size = 0
        self.__max_pool_size = pool_size
        self.__pool = Queue(maxsize=pool_size)

    def __create_connection(self) -> "SMTP":
        connection = SMTP(self.__host, self.__port)
        connection.connect(self.__host, self.__port)
        connection.ehlo()
        connection.starttls()
        connection.ehlo()
        connection.login(self.__username, self.__password)
        return connection

    def get_connection(self) -> "SMTP":
        with self.__lock:
            if not self.__pool.empty():
                return self.__pool.get()

            elif self.__current_pool_size < self.__max_pool_size:
                connection = self.__create_connection()
                self.__current_pool_size += 1
                return connection

            return self.__pool.get()

    def return_connection(self, connection: "SMTP") -> None:
        with self.__lock:
            self.__pool.put(connection)

    def close_connections(self) -> None:
        while not self.__pool.empty():
            connection = self.__pool.get()
            connection.quit()
            self.__current_pool_size -= 1


async def send_mail(mail: dict):
    outgoing_mail = mail["outgoing_mail"]
    recipients = mail.get("recipients", [])
    parsed_message = Parser(policy=policy.default).parsestr(mail["message"])

    for type in ["To", "Cc", "Bcc"]:
        if rcpts := parsed_message[type]:
            for rcpt in rcpts.split(","):
                recipients.append(rcpt.strip())

    del parsed_message["Bcc"]

    sender = parsed_message["From"]
    message = parsed_message.as_string()
    host = os.getenv("HARAKA_HOST")
    port = os.getenv("HARAKA_PORT")
    username = os.getenv("HARAKA_USERNAME")
    password = os.getenv("HARAKA_PASSWORD")
    smtp_pool = SMTPConnectionPool(host, port, username, password)
    connection = smtp_pool.get_connection()
    connection.sendmail(sender, recipients, message)
    print(f"Message {outgoing_mail} From `{sender}` To `{recipients}`.")
