import os
import json
import click
import distro
import platform
import subprocess
from dotenv import load_dotenv
from mail_agent.haraka import Haraka
from mail_agent.utils import replace_env_vars, create_systemd_service


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option(
    "--prod",
    "--production",
    is_flag=True,
    help="Setup the Mail Agent for production.",
    default=False,
)
def setup(prod) -> None:
    """Setup the Mail Agent by reading the configuration from the config.json file."""

    if prod:
        setup_for_production()
    else:
        setup_for_development()


@cli.command()
def start() -> None:
    """Start the Mail Agent using Honcho."""

    subprocess.run(["honcho", "start"])


def setup_for_production() -> None:
    """Setup the Mail Agent for production."""

    if not (platform.system() == "Linux" and distro.id() == "ubuntu"):
        click.echo("[X] This setup is only supported on Ubuntu Linux.")
        return

    click.echo("[X] Setting up the Mail Agent for production ...")
    config = get_config()
    install_node_packages(for_production=True)
    install_haraka_globally()
    setup_haraka(config["haraka"])
    generate_procfile(config, for_production=True)
    install_and_setup_rabbitmq(config["rabbitmq"])
    create_haraka_service()

    if config["haraka"]["agent_type"] == "Outbound":
        create_mail_agent_service()

    click.echo("[X] Setup complete!")


def setup_for_development() -> None:
    """Setup the Mail Agent for development."""

    click.echo("[X] Setting up the Mail Agent for development ...")
    config = get_config()
    install_node_packages(for_production=False)
    setup_haraka(config["haraka"])
    generate_procfile(config, for_production=False)
    click.echo("[X] Setup complete!")


def get_config() -> dict:
    """Return the configuration from the config.json file."""

    click.echo("[X] Reading configuration from config.json ...")
    with open("config.json", "r") as config_file:
        config = json.load(config_file)

        click.echo("[X] Loading environment variables ...")
        load_dotenv()
        replace_env_vars(config)

        return config


def install_node_packages(for_production: bool = False) -> None:
    """Install the required Node.js packages."""

    click.echo("[X] Installing Node.js packages ...")
    command = ["yarn", "install", "--silent"]
    if for_production:
        command.append("--prod")

    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def install_haraka_globally() -> None:
    """Install Haraka globally using Yarn."""

    click.echo("[X] Installing Haraka globally ...")
    subprocess.run(
        ["npm", "install", "-g", "Haraka", "--silent"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def setup_haraka(haraka_config: dict) -> None:
    """Setup the Haraka mail server configuration."""

    click.echo("[X] Setting up Haraka MTA ...")
    haraka = Haraka()
    haraka.setup(haraka_config)


def generate_procfile(config: dict, for_production: bool = False) -> None:
    """Generate a Procfile based on the consumers configuration in the config.json file."""

    click.echo("[X] Generating Procfile ...")

    lines = []
    if not for_production:
        rabbitmq_config = config["rabbitmq"]
        depends_on_service = (
            f'./wait.sh "RabbitMQ" {rabbitmq_config["port"]} {rabbitmq_config["host"]}'
        )
        lines = [f"haraka: {depends_on_service} npx haraka -c ."]

    haraka_config = config["haraka"]
    consumers_config = config["consumers"]
    if haraka_config["agent_type"] == "Outbound":
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


def install_and_setup_rabbitmq(rabbitmq_config: dict) -> None:
    """Install and setup RabbitMQ based on the configuration in the config.json file."""

    def execute_command(command):
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True,
        )

    click.echo("[X] Installing and setting up RabbitMQ ...")

    # Update system packages
    execute_command("sudo apt update && sudo apt upgrade -y")

    # Install Erlang
    execute_command("sudo apt install -y erlang")

    # Add RabbitMQ signing key
    execute_command(
        "wget -O- https://packages.rabbitmq.com/rabbitmq-release-signing-key.asc | sudo apt-key add -"
    )

    # Add RabbitMQ repository
    execute_command(
        'echo "deb https://dl.bintray.com/rabbitmq-erlang/debian $(lsb_release -cs) erlang" | sudo tee /etc/apt/sources.list.d/bintray.rabbitmq.list'
    )
    execute_command(
        'echo "deb https://dl.bintray.com/rabbitmq/debian $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/bintray.rabbitmq.list'
    )

    # Install RabbitMQ
    execute_command("sudo apt update")
    execute_command("sudo apt install rabbitmq-server -y")

    # Enable and start RabbitMQ
    execute_command("sudo systemctl enable rabbitmq-server")
    execute_command("sudo systemctl restart rabbitmq-server")

    # Enable RabbitMQ management plugin
    execute_command("sudo rabbitmq-plugins enable rabbitmq_management")

    # Create RabbitMQ user
    rabbitmq_username = rabbitmq_config["username"]
    rabbitmq_password = rabbitmq_config["password"]
    execute_command(
        f"sudo rabbitmqctl add_user {rabbitmq_username} {rabbitmq_password}"
    )
    execute_command(f"sudo rabbitmqctl set_user_tags {rabbitmq_username} administrator")
    execute_command(
        f'sudo rabbitmqctl set_permissions -p / {rabbitmq_username} ".*" ".*" ".*"'
    )

    # Remove guest user
    execute_command("sudo rabbitmqctl delete_user guest")


def create_haraka_service() -> None:
    """Create a systemd service for the Haraka mail server."""

    print("[X] Generating haraka.service [systemd] ...")

    app_dir = os.getcwd()
    create_systemd_service("haraka.service", app_dir=app_dir)


def create_mail_agent_service() -> None:
    """Create a systemd service for the Mail Agent."""

    print("[X] Generating mail-agent.service [systemd] ...")

    app_dir = os.getcwd()
    app_bin = os.path.join(app_dir, "venv/bin")
    create_systemd_service("mail-agent.service", app_dir=app_dir, app_bin=app_bin)
