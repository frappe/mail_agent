import os
import json
import click
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

    click.echo("[X] Setting up the Mail Agent for production ...")
    config = get_config()
    install_node_packages(for_production=True)
    install_haraka_globally()
    setup_haraka(config["haraka"])
    generate_procfile(config["consumers"], for_production=True)
    create_haraka_service()
    create_mail_agent_service()
    click.echo("[X] Setup complete!")


def setup_for_development() -> None:
    """Setup the Mail Agent for development."""

    click.echo("[X] Setting up the Mail Agent for development ...")
    config = get_config()
    install_node_packages(for_production=False)
    setup_haraka(config["haraka"])
    generate_procfile(config["consumers"], for_production=False)
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
    subprocess.run(["npm", "install", "-g", "Haraka", "--silent"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def setup_haraka(haraka_config: dict) -> None:
    """Setup the Haraka mail server configuration."""

    click.echo("[X] Setting up Haraka MTA ...")
    haraka = Haraka()
    haraka.setup(haraka_config)


def generate_procfile(consumers_config: dict, for_production: bool = False) -> None:
    """Generate a Procfile based on the consumers configuration in the config.json file."""

    click.echo("[X] Generating Procfile ...")

    lines = []
    for queue, consumer_config in consumers_config.items():
        workers = consumer_config["workers"]
        for worker in range(1, workers + 1):
            worker_name = (
                f"consumer-{queue.replace('::', '-').replace('_', '-')}-{worker}"
            )
            line = f"{worker_name}: python mail_agent/app.py {queue} {worker}"
            lines.append(line)

    if not for_production:
        lines += ["", "haraka: npx haraka -c ."]

    with open("Procfile", "w") as f:
        f.write("\n".join(lines))


def create_haraka_service() -> None:
    """Create a systemd service for the Haraka mail server."""

    print("[X] Generating haraka.service [systemd] ...")

    app_dir = os.getcwd()
    create_systemd_service("haraka.service", app_dir=app_dir)


def create_mail_agent_service() -> None:
    """Create a systemd service for the Mail Agent."""

    print("[X] Generating mail-agent.service [systemd] ...")

    app_dir = os.getcwd()
    app_bin = os.path.join(app_dir, "env/bin")
    create_systemd_service("mail-agent.service", app_dir=app_dir, app_bin=app_bin)
