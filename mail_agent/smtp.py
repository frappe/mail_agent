import os
import time
import threading
from queue import Queue
from email import policy
from smtplib import SMTP
from email.parser import Parser


host = os.getenv("HARAKA_HOST", "localhost")
port = int(os.getenv("HARAKA_PORT", 25))
username = os.getenv("HARAKA_USERNAME", None)
password = os.getenv("HARAKA_PASSWORD", None)
max_emails_per_second = float(os.getenv("MAX_EMAILS_PER_SECOND_PER_WORKER", 0.5))


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

            self._lock = threading.Lock()
            self._condition = threading.Condition(self._lock)
            self._pool_size = pool_size
            self._pool = Queue(maxsize=pool_size)
            self._initialized = True

    def __create_new_connection(self) -> SMTP:
        """Create a new SMTP connection."""

        connection = SMTP(self.__host, self.__port)
        connection.connect(self.__host, self.__port)
        connection.ehlo()
        connection.starttls()
        connection.ehlo()

        if self.__username and self.__password:
            connection.login(self.__username, self.__password)

        return connection

    def get_connection(self) -> SMTP:
        """Returns a SMTP connection from the pool."""

        with self._condition:
            while self._pool.empty():
                if self._pool.qsize() < self._pool_size:
                    return self.__create_new_connection()
                if not self._condition.wait(timeout=5):
                    raise RuntimeError("No connections available in the pool.")

            return self._pool.get()

    def return_connection(self, connection: SMTP) -> None:
        """Return an SMTP connection to the pool."""

        with self._condition:
            if self._pool.full():
                connection.quit()
            else:
                self._pool.put(connection)
                self._condition.notify()

    def close_connections(self) -> None:
        """Close all SMTP connections in the pool."""

        with self._condition:
            while not self._pool.empty():
                connection: SMTP = self._pool.get()
                connection.quit()

            self._condition.notify_all()


class EmailRateLimiter:
    _instance = None

    def __new__(cls, *args, **kwargs) -> "EmailRateLimiter":
        """Singleton pattern to ensure only one instance of the rate limiter is created."""

        if not cls._instance:
            cls._instance = super(EmailRateLimiter, cls).__new__(cls)

        return cls._instance

    def __init__(self, max_emails_per_second: float = 0) -> None:
        """Initialize the rate limiter with the desired email sending rate."""

        if not hasattr(self, "_initialized"):  # Ensure __init__ is run only once
            self.max_emails_per_second = max_emails_per_second
            self.emails_sent = 0
            self.start_time = time.time()
            self._initialized = True

    def throttle(self) -> None:
        """Throttle email sending to maintain the desired rate."""

        if self.max_emails_per_second <= 0:
            return

        self.emails_sent += 1
        elapsed_time = time.time() - self.start_time
        expected_emails = elapsed_time * self.max_emails_per_second

        if self.emails_sent > expected_emails:
            sleep_time = (self.emails_sent / self.max_emails_per_second) - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.start_time = time.time()
            self.emails_sent = 0
        else:
            self.start_time = time.time()
            self.emails_sent = 0


def get_rate_limiter() -> EmailRateLimiter:
    """Returns the singleton instance of the rate limiter."""

    return EmailRateLimiter(max_emails_per_second=max_emails_per_second)


def send_mail(mail: dict) -> None:
    """Send an email message using the SMTP connection pool, with rate limiting."""

    global host, port, username, password
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
    smtp_pool = SMTPConnectionPool(host, port, username, password)

    try:
        connection = smtp_pool.get_connection()
        rate_limiter = get_rate_limiter()
        connection.sendmail(sender, recipients, message)
        print(f"Message {outgoing_mail} From `{sender}` To `{recipients}`.")
        rate_limiter.throttle()
    finally:
        if connection:
            smtp_pool.return_connection(connection)
