import sys
import json
from mail_agent import app


if __name__ == "__main__":
    try:
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print("config.json file not found")
        sys.exit(1)

    app.run(config)
