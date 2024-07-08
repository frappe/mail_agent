import json
from dotenv import load_dotenv
from mail_agent.haraka import Haraka
from mail_agent.utils import replace_env_vars


def setup():
    """Setup the Mail Agent by reading the configuration from the config.json file."""

    with open("config.json") as config_file:
        config = json.load(config_file)

    replace_env_vars(config)
    setup_haraka(config["haraka"])
    generate_procfile(config["consumers"])


def setup_haraka(haraka_config: dict):
    """Setup the Haraka mail server configuration."""

    haraka = Haraka()
    haraka.setup(haraka_config)


def generate_procfile(consumers_config: dict):
    """Generate a Procfile based on the consumers configuration in the config.json file."""

    lines = []
    for queue, consumer_config in consumers_config.items():
        workers = consumer_config["workers"]
        for worker in range(1, workers + 1):
            worker_name = f"consumer-{queue.replace('::', '-').replace('_', '-')}-{worker}"
            line = f"{worker_name}: python mail_agent/app.py {queue} {worker}"
            lines.append(line)

    with open("Procfile", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    load_dotenv()
    setup()
