import os
import sys
import crypt
import shutil
import importlib
import subprocess
import configparser
from pathlib import Path
from typing import Any, Literal


def execute_command(command: str | list[str]) -> tuple[str, str]:
    if isinstance(command, str):
        command = command.split()

    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stderr, result.stdout
    except Exception as e:
        return "", str(e)


def create_directory(directory: str) -> None:
    Path(directory).mkdir(parents=True, exist_ok=True)


def remove_directory(directory: str) -> None:
    if directory and Path(directory).exists():
        shutil.rmtree(directory)


def file_exists(file_path: str) -> bool:
    return Path(file_path).exists()


def create_file(file_path: str) -> None:
    Path(file_path).touch(exist_ok=True)


def write_file(file_path: str, content: str, mode: Literal["w", "a"] = "w") -> None:
    with open(file_path, mode) as file:
        file.write(content or "")


def read_file(file_path: str) -> str | None:
    return Path(file_path).read_text() if file_exists(file_path) else None


def update_ini_config(file_path: str, section: str, key: str, value: str) -> None:
    if not file_exists(file_path):
        create_file(file_path)

    config = configparser.ConfigParser()
    config.read(file_path)

    if section not in config:
        config.add_section(section)

    config.set(section, key, value)
    with open(file_path, "w") as f:
        config.write(f)


def remove_ini_config(file_path: str, section: str, key: str) -> None:
    config = configparser.ConfigParser()
    config.read(file_path)

    if section in config and key in config[section]:
        config.remove_option(section, key)

    with open(file_path, "w") as f:
        config.write(f)


def get_encrypted_password(password: str, salt: str | None = None) -> str:
    if not salt:
        salt = crypt.mksalt(crypt.METHOD_SHA512)

    return crypt.crypt(password, salt)


def get_attr(module_name: str, function_name: str) -> callable:
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)

    return function


def replace_env_vars(config: Any) -> Any:
    if isinstance(config, dict):
        for key, value in config.items():
            config[key] = replace_env_vars(value)
    elif isinstance(config, list):
        config = [replace_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        env_var = config[2:-1]
        config = os.getenv(env_var)

        if not config:
            print(f"Error: Environment variable {env_var} is not set")
            sys.exit(1)

    return config


def generate_systemd_service(
    template: str, enable: bool = True, restart: bool = True, **kwargs
):
    cwd = os.getcwd()
    template_dir = os.path.join(cwd, "mail_agent/templates")
    template_path = os.path.join(template_dir, template)
    service_dir = os.path.join(cwd, "mail_agent/services")
    service_path = os.path.join(service_dir, template)
    systemd_path = f"/etc/systemd/system/{template}"

    with open(template_path, "r") as template_file:
        template_content = template_file.read()

    service_content = template_content.format(**kwargs)
    create_directory(service_dir)

    with open(service_path, "w") as service_file:
        service_file.write(service_content)

    subprocess.run(["sudo", "cp", service_path, systemd_path], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    if enable:
        subprocess.run(["sudo", "systemctl", "enable", template], check=True)
    if restart:
        subprocess.run(["sudo", "systemctl", "restart", template], check=True)
