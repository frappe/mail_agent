import json
import click
import subprocess
from dotenv import load_dotenv
from mail_agent.haraka import Haraka
from mail_agent.utils import replace_env_vars


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--prod",
    "--production",
    is_flag=True,
    help="Setup the Mail Agent for production.",
    default=False,
)
def setup(prod):
    """Setup the Mail Agent by reading the configuration from the config.json file."""

    if prod:
        click.echo("[X] Setting up the Mail Agent for production...")
    else:
        click.echo("[X] Setting up the Mail Agent for development...")

    click.echo("[X] Reading configuration from config.json...")
    with open("config.json") as config_file:
        config = json.load(config_file)

    click.echo("[X] Loading environment variables...")
    load_dotenv()
    replace_env_vars(config)

    click.echo("[X] Installing Node.js packages...")
    install_node_packages(prod)

    click.echo("[X] Setting up Haraka MTA...")
    setup_haraka(config["haraka"])

    click.echo("[X] Generating Procfile...")
    generate_procfile(config["consumers"], prod)


@cli.command()
def start():
    """Start the Mail Agent using Honcho."""

    subprocess.run(["honcho", "start"])


def install_node_packages(for_production: bool = False):
    """Install the required Node.js packages."""

    command = ["yarn", "install"]
    if for_production:
        command.append("--prod")

    subprocess.run(command)


def setup_haraka(haraka_config: dict):
    """Setup the Haraka mail server configuration."""

    haraka = Haraka()
    haraka.setup(haraka_config)


def generate_procfile(consumers_config: dict, for_production: bool = False):
    """Generate a Procfile based on the consumers configuration in the config.json file."""

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
