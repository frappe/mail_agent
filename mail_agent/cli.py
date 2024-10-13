import os
import json
import click
import distro
import platform
import subprocess
from dotenv import load_dotenv
from mail_agent.haraka import Haraka
from mail_agent.rabbitmq import RabbitMQ
from mail_agent.utils import (
    write_file,
    execute_command,
    replace_env_vars,
    generate_password,
    create_systemd_service,
)


@click.group()
def cli() -> None:
    """Mail Agent CLI for setting up and managing the Mail Agent."""

    pass


@cli.command()
@click.option(
    "--prod",
    is_flag=True,
    help="Setup the Mail Agent for production on Ubuntu Linux.",
    default=False,
)
@click.option(
    "--inbound",
    is_flag=True,
    help="Setup the Mail Agent as an Inbound server.",
    default=False,
)
def setup(prod: bool = False, inbound: bool = False) -> None:
    """Setup the Mail Agent by reading the configuration from the config.json file."""

    if prod and not (platform.system() == "Linux" and distro.id() == "ubuntu"):
        click.echo("❌ [ERROR] Production setup is only supported on Ubuntu Linux.")
        return

    click.echo("🛠️ [INFO] Initiating Mail Agent setup...")
    agent_type = "inbound" if inbound else "outbound"
    me = ask_for_input(
        "Hostname", execute_command("hostname -f")[1].strip(), required=True
    )

    env_vars = {
        "AGENT_ID": ask_for_input("Agent ID", me),
        "AGENT_TYPE": agent_type,
        "HARAKA_HOST": ask_for_input("Haraka Host", "localhost"),
        "HARAKA_PORT": ask_for_input("Haraka Port", 25),
        "HARAKA_USERNAME": "frappe",
        "HARAKA_PASSWORD": generate_password(),
        "RABBITMQ_HOST": ask_for_input(
            "RabbitMQ Host", "localhost" if not prod else None, required=True
        ),
        "RABBITMQ_PORT": ask_for_input("RabbitMQ Port", 5672),
        "RABBITMQ_VIRTUAL_HOST": ask_for_input("RabbitMQ Virtual Host", "/"),
        "RABBITMQ_USERNAME": ask_for_input(
            "RabbitMQ Username", "guest" if not prod else me
        ),
        "RABBITMQ_PASSWORD": ask_for_input(
            "RabbitMQ Password",
            "guest" if not prod else None,
            required=True,
            hide_input=True,
        ),
    }

    if agent_type == "inbound":
        env_vars["FRAPPE_BLACKLIST_HOST"] = ask_for_input(
            "Frappe Blacklist Host", "https://frappemail.com"
        )
    else:
        env_vars["MAX_EMAILS_PER_SECOND_PER_WORKER"] = ask_for_input(
            "Max Emails Per Second Per Worker", 0.5
        )

    test_rabbitmq_connection(env_vars)
    generate_env_file(env_vars)

    config = get_config()
    config["haraka"].update(
        {
            "me": me,
            "agent_type": agent_type,
            "tls_key_path": None,
            "tls_cert_path": None,
        }
    )

    if prod:
        config["haraka"]["tls_key_path"] = ask_for_input(
            "TLS Key Path", f"/etc/letsencrypt/live/{me}/privkey.pem"
        )
        config["haraka"]["tls_cert_path"] = ask_for_input(
            "TLS Cert Path", f"/etc/letsencrypt/live/{me}/cert.pem"
        )
        setup_for_production(config)
    else:
        setup_for_development(config)


@cli.command()
def start() -> None:
    """Start the Mail Agent using Honcho."""

    click.echo("🚀 [INFO] Starting the Mail Agent with Honcho...")
    subprocess.run(["honcho", "start"])


def setup_for_production(config: dict) -> None:
    """Setup the Mail Agent for production."""

    click.echo("🔧 [INFO] Setting up the Mail Agent for production...")
    install_node_packages(for_production=True)
    install_haraka_globally()
    setup_haraka(config["haraka"], for_production=True)
    generate_procfile(config, for_production=True)
    create_haraka_service()

    if config["haraka"]["agent_type"] == "outbound":
        create_mail_agent_service()

    click.echo("✅ [SUCCESS] Production setup complete!")


def setup_for_development(config: dict) -> None:
    """Setup the Mail Agent for development."""

    click.echo("🔧 [INFO] Setting up the Mail Agent for development...")
    install_node_packages()
    setup_haraka(config["haraka"])
    generate_procfile(config)
    click.echo("✅ [SUCCESS] Development setup complete!")


def ask_for_input(
    prompt: str,
    default: str | int | None = None,
    required: bool = False,
    hide_input: bool = False,
) -> str:
    """Ask for user input with an optional default value."""

    if required:
        return click.prompt(
            f"🔹 {prompt}", default=default, hide_input=hide_input
        ) or ask_for_input(
            prompt, default=default, required=True, hide_input=hide_input
        )

    return click.prompt(f"🔹 {prompt}", default=default, hide_input=hide_input)


def test_rabbitmq_connection(env_vars: dict) -> None:
    """Test the RabbitMQ connection."""

    click.echo("🔗 [INFO] Testing RabbitMQ connection...")

    rmq = RabbitMQ(
        host=env_vars["RABBITMQ_HOST"],
        port=env_vars["RABBITMQ_PORT"],
        virtual_host=env_vars["RABBITMQ_VIRTUAL_HOST"],
        username=env_vars["RABBITMQ_USERNAME"],
        password=env_vars["RABBITMQ_PASSWORD"],
    )
    rmq._disconnect()

    click.echo("✅ [SUCCESS] RabbitMQ connection successful!")


def generate_env_file(env_vars: dict) -> None:
    """Generates a .env file in the current directory with the provided environment variables."""

    click.echo("📜 [INFO] Generating .env file...")

    content = ""
    for key, value in env_vars.items():
        content += f"{key}={value}\n"

    env_file_path = os.path.join(os.getcwd(), ".env")
    write_file(env_file_path, content)

    click.echo(f"✅ [INFO] .env file created at: {env_file_path}")


def get_config() -> dict:
    """Return the configuration from the config.json file."""

    click.echo("📄 [INFO] Reading configuration from config.json...")
    with open("config.json", "r") as config_file:
        config = json.load(config_file)

    click.echo("🔄 [INFO] Loading environment variables...")
    load_dotenv(override=False)
    replace_env_vars(config)

    return config


def install_node_packages(for_production: bool = False) -> None:
    """Install the required Node.js packages."""

    click.echo("📦 [INFO] Installing Node.js packages...")
    command = ["yarn", "install", "--silent"]
    if for_production:
        command.append("--prod")

    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def install_haraka_globally() -> None:
    """Install Haraka globally."""

    click.echo("🌍 [INFO] Installing Haraka globally...")
    subprocess.run(
        ["npm", "install", "-g", "Haraka@3.0.3", "--silent"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def setup_haraka(haraka_config: dict, for_production: bool = False) -> None:
    """Setup the Haraka mail server configuration."""

    click.echo("⚙️ [INFO] Configuring Haraka MTA...")

    if for_production:
        additional_plugins = {
            "inbound": ["ip_blacklist", "enforce_rdns"],
            "outbound": [],
        }

        for type, plugins in additional_plugins.items():
            for plugin in plugins:
                if plugin not in haraka_config["plugins"][type]:
                    haraka_config["plugins"][type].append(plugin)

    haraka = Haraka()
    haraka.setup(haraka_config)


def generate_procfile(config: dict, for_production: bool = False) -> None:
    """Generate a Procfile based on the consumers configuration in the config.json file."""

    click.echo("📝 [INFO] Generating Procfile...")

    lines = []
    if not for_production:
        rabbitmq_config = config["rabbitmq"]
        depends_on_service = (
            f'./wait.sh "RabbitMQ" {rabbitmq_config["port"]} {rabbitmq_config["host"]}'
        )
        lines = [f"haraka: {depends_on_service} npx haraka -c ."]

    haraka_config = config["haraka"]
    consumers_config = config["consumers"]
    if haraka_config["agent_type"] == "outbound":
        depends_on_service = (
            f'./wait.sh "Haraka" {haraka_config["port"]} {haraka_config["host"]}'
        )
        for queue, consumer_config in consumers_config.items():
            workers = consumer_config["workers"]
            for worker in range(1, workers + 1):
                worker_name = (
                    f"consumer-{queue.replace('::', '-').replace('_', '-')}-{worker}"
                )
                line = f"{worker_name}: {depends_on_service} python mail_agent/app.py {queue} {worker}"
                lines.append(line)

    with open("Procfile", "w") as f:
        f.write("\n".join(lines))


def create_haraka_service() -> None:
    """Create a systemd service for the Haraka mail server."""

    click.echo("🛠️ [INFO] Creating haraka.service [systemd]...")
    app_dir = os.getcwd()
    create_systemd_service("haraka.service", app_dir=app_dir)


def create_mail_agent_service() -> None:
    """Create a systemd service for the Mail Agent."""

    click.echo("🛠️ [INFO] Creating mail-agent.service [systemd]...")
    app_dir = os.getcwd()
    app_bin = os.path.join(app_dir, "venv/bin")
    create_systemd_service("mail-agent.service", app_dir=app_dir, app_bin=app_bin)


def execute_in_shell(command) -> None:
    """Execute a command in the shell."""

    subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
    )
