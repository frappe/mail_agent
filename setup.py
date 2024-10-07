from setuptools import setup, find_packages


def get_requirements() -> list[str]:
    """Returns the requirements from the requirements.txt"""

    with open("requirements.txt") as f:
        return f.read().strip().split("\n")


setup(
    name="mail-agent",
    version="0.0.1",
    packages=find_packages(),
    include_package_data=True,
    author="Frappe Technologies Pvt. Ltd.",
    author_email="developers@frappe.io",
    description="Frappe Mail Agent",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/frappe/mail_agent",
    zip_safe=False,
    python_requires=">=3.10",
    install_requires=get_requirements(),
    entry_points={
        "console_scripts": [
            "mail-agent = mail_agent.cli:cli",
        ],
    },
)
