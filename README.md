# Mail Agent

## Installation

Get started with Mail Agent by following these steps:

```bash
git clone https://github.com/frappe/mail_agent
cd mail_agent
virtualenv venv
source venv/bin/activate
pip install .
```

## Setup

### Development

Follow these steps to set up Mail Agent for development:

- #### Prerequisites

  Before setting up Mail Agent, ensure you have the following:

  - **Yarn**: A package manager that simplifies working with JavaScript projects.
    ```bash
    npm install --global yarn
    ```

- #### Set Up Mail Agent

  This command will install Node packages, set up Haraka, and generate a Procfile to manage processes.

  ```bash
  mail-agent setup
  ```

- #### Start Mail Agent
  ```bash
  mail-agent start
  ```

### Production (Ubuntu)

For production deployment on Ubuntu, follow these steps:

- #### Install Required Packages

  Ensure you have the necessary tools and libraries installed:

  ```bash
  sudo apt install curl build-essential -y
  ```

- #### Install Node.js, npm, and Yarn

  Set up Node.js and Yarn, which are required for running `Haraka`:

  ```bash
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
  sudo npm install -g yarn
  ```

- #### Obtain a TLS Certificate (Optional)

  If you want to obtain TLS certificate for your Mail Agent from Let's Encrypt, follow these steps:

  - Install Certbot:
    ```bash
    sudo apt install certbot -y
    ```
  - Generate a TLS certificate for your host:
    ```bash
    sudo certbot certonly --standalone -d $(hostname -f)
    ```

- #### Set Up Mail Agent

  This command will install Node packages, set up Haraka, generate a Procfile and create systemd services:

  ```bash
  mail-agent setup --prod   # Use --inbound to setup agent for inbound
  ```

- #### Verify Services

  Ensure that all services are running correctly:

  ```bash
  sudo systemctl status haraka

  # Inbound
  sudo systemctl status spamassassin

  # Outbound
  sudo systemctl status mail-agent
  ```

## License

[GNU Affero General Public License v3.0](https://github.com/frappe/mail_agent/blob/develop/license.txt)
