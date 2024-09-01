import os
from mail_agent.utils import (
    write_file,
    create_file,
    execute_command,
    update_ini_config,
    remove_ini_config,
    get_encrypted_password,
)


class Haraka:
    def __init__(self) -> None:
        """Initializes the Haraka class."""

        self.haraka_local = os.getcwd()
        self.config_files = {
            "me": "config/me",
            "plugins": "config/plugins",
            "tls.ini": "config/tls.ini",
            "smtp.ini": "config/smtp.ini",
            "outbound.ini": "config/outbound.ini",
            "relay_acl_allow": "config/relay_acl_allow",
            "spamassassin.ini": "config/spamassassin.ini",
            "auth_enc_file.ini": "config/auth_enc_file.ini",
        }

    @staticmethod
    def get_status() -> str:
        """Returns the status of the Haraka service."""

        error, output = execute_command("sudo systemctl status haraka")
        return error or output

    @staticmethod
    def restart() -> None:
        """Restarts the Haraka service."""

        execute_command("sudo systemctl restart haraka")

    def get_file_path(self, file_key: str) -> str:
        """Returns the file path for the given file key."""

        return os.path.join(self.haraka_local, self.config_files[file_key])

    def setup(self, config: dict) -> None:
        """Sets up the Haraka configuration."""

        for file_key, file_path in self.config_files.items():
            create_file(self.get_file_path(file_key))

        if config["agent_type"] == "outbound":
            update_ini_config(
                self.get_file_path("outbound.ini"),
                "main",
                "received_header",
                config["received_header"],
            )
            write_file(self.get_file_path("relay_acl_allow"), config["relay_acl_allow"])
            update_ini_config(
                self.get_file_path("auth_enc_file.ini"),
                "users",
                config["username"],
                get_encrypted_password(config["password"]),
            )
        else:
            spamassassin_config = {
                "host": config["spamassassin_host"],
                "port": config["spamassassin_port"],
            }
            for key, value in spamassassin_config.items():
                update_ini_config(
                    self.get_file_path("spamassassin.ini"), "main", key, str(value)
                )

        smtp_config = {
            "listen": f"[::0]:{config['port']}",
            "nodes": str(config["nodes"]),
            "max_lines": "1000",
            "max_received": "100",
        }
        for key, value in smtp_config.items():
            update_ini_config(self.get_file_path("smtp.ini"), "main", key, value)

        write_file(self.get_file_path("me"), config["me"])
        write_file(
            self.get_file_path("plugins"),
            "\n".join(config["plugins"][config["agent_type"]]),
        )

        if config["tls_key_path"] and config["tls_cert_path"]:
            update_ini_config(
                self.get_file_path("tls.ini"), "main", "key", config["tls_key_path"]
            )
            update_ini_config(
                self.get_file_path("tls.ini"), "main", "cert", config["tls_cert_path"]
            )
        else:
            remove_ini_config(self.get_file_path("tls.ini"), "main", "key")
            remove_ini_config(self.get_file_path("tls.ini"), "main", "cert")
            generate_self_signed_tls_certificate()


def generate_self_signed_tls_certificate(
    country_name: str = "IN",
    state_or_province_name: str = "Maharashtra",
    locality_name: str = "Mumbai",
    organization_name: str = "Frappe Technologies Pvt. Ltd.",
    common_name: str = "frappe.io",
    key_size: int = 2048,
) -> None:
    """Generates a self-signed TLS certificate."""

    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import hashes, serialization

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country_name),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
            x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )
    public_key = private_key.public_key()

    certificate_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = certificate_builder.public_bytes(encoding=serialization.Encoding.PEM)

    config_dir = os.path.join(os.getcwd(), "config")
    key_pem_path = os.path.join(config_dir, "tls_key.pem")
    cert_pem_path = os.path.join(config_dir, "tls_cert.pem")

    with open(key_pem_path, "wb") as f:
        f.write(key_pem)

    with open(cert_pem_path, "wb") as f:
        f.write(cert_pem)
