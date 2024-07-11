# Mail Agent

## Prerequisite

- [Yarn](https://classic.yarnpkg.com/)
  ```bash
  npm install --global yarn
  ```
- [RabbitMQ](https://www.rabbitmq.com/)
  ```bash
  docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management
  ```

## Installation

```bash
git clone https://github.com/frappe/mail_agent && cd mail_agent
virtualenv venv && source venv/bin/activate
pip install --editable .
```

## Setup

```bash
mail-agent setup
```

## Running

```bash
mail-agent start
```
