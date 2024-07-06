# Mail Agent

## Installation

```bash
git clone https://github.com/frappe/mail_agent
cd mail_agent
virtualenv env
source env/bin/activate
pip install -r requirements.txt
```

## Setup

```bash
# Haraka
export HARAKA_AGENT_TYPE="Outbound"
export HARAKA_USERNAME="frappe"
export HARAKA_PASSWORD="frappe"
export HARAKA_PORT=25

# RabbitMQ
export RABBITMQ_HOST="localhost"
export RABBITMQ_PORT=5672
export RABBITMQ_USERNAME="guest"
export RABBITMQ_PASSWORD="guest"
```

## Running

```bash
python setup.py
```
