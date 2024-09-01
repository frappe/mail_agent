from setuptools import setup, find_packages


def get_requirements() -> list[str]:
    """Returns the requirements from the requirements.txt"""

    with open("requirements.txt") as f:
        return f.read().strip().split("\n")


setup(
    name="mail-agent",
    version="0.0.1",
    description="Frappe Mail Agent",
    author="Frappe Technologies Pvt. Ltd.",
    author_email="developers@frappe.io",
    url="https://github.com/frappe/mail_agent",
    packages=find_packages(),
    zip_safe=False,
    install_requires=get_requirements(),
    entry_points={
        "console_scripts": [
            "mail-agent = mail_agent.cli:cli",
        ],
    },
)
