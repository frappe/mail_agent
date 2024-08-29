import os
from email import policy
from smtplib import SMTP
from threading import Lock
from queue import Queue, Empty
from email.parser import Parser


host = os.getenv("HARAKA_HOST", "localhost")
port = int(os.getenv("HARAKA_PORT", 25))


class SMTPConnectionPool:
    _instance = None

    def __new__(cls, *args, **kwargs) -> "SMTPConnectionPool":
        """Singleton pattern to ensure only one instance of the class is created."""

        if not cls._instance:
            cls._instance = super(SMTPConnectionPool, cls).__new__(cls)

        return cls._instance

    def __init__(
        self,
        host: str = "localhost",
        port: int = 25,
        username: str | None = None,
        password: str | None = None,
        pool_size: int = 5,
    ) -> None:
        """Initialize the SMTP connection pool."""

        if not hasattr(self, "_initialized"):  # Ensure __init__ is run only once
            self.__host = host
            self.__port = port
            self.__username = username
            self.__password = password

            self._lock = Lock()
            self._pool_size = pool_size
            self._pool = Queue(maxsize=pool_size)
            self._initialized = True

    def __create_new_connection(self) -> None:
        """Create a new SMTP connection and add it to the pool."""

        connection = SMTP(self.__host, self.__port)
        connection.connect(self.__host, self.__port)
        connection.ehlo()
        connection.starttls()
        connection.ehlo()

        if self.__username and self.__password:
            connection.login(self.__username, self.__password)

        self._pool.put(connection)

    def get_connection(self) -> SMTP:
        """Get an SMTP connection from the pool."""

        with self._lock:
            if self._pool.empty() and self._pool.qsize() < self._pool_size:
                self.__create_new_connection()

            try:
                return self._pool.get(timeout=5)
            except Empty:
                raise RuntimeError("No connections available in the pool.")

    def return_connection(self, connection: SMTP) -> None:
        """Return an SMTP connection to the pool."""

        with self._lock:
            if self._pool.full():
                connection.quit()  # Close connection if pool is full
            else:
                self._pool.put(connection)

    def close_connections(self) -> None:
        """Close all SMTP connections in the pool."""

        with self._lock:
            while not self._pool.empty():
                connection = self._pool.get()
                connection.quit()


def send_mail(mail: dict) -> None:
    """Send an email message using the SMTP connection pool."""

    global host, port
    outgoing_mail = mail["outgoing_mail"]
    recipients = mail.get("recipients", [])
    parsed_message = Parser(policy=policy.default).parsestr(mail["message"])

    if not recipients:
        for type in ["To", "Cc", "Bcc"]:
            if rcpts := parsed_message[type]:
                for rcpt in rcpts.split(","):
                    recipients.append(rcpt.strip())

    del parsed_message["Bcc"]

    sender = parsed_message["From"]
    message = parsed_message.as_string()
    smtp_pool = SMTPConnectionPool(host, port)
    connection = smtp_pool.get_connection()

    try:
        connection.sendmail(sender, recipients, message)
        print(f"Message {outgoing_mail} From `{sender}` To `{recipients}`.")
    finally:
        smtp_pool.return_connection(connection)
