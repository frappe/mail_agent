#!/bin/bash

SERVICE_NAME=$1
PORT=$2
NEXT_COMMAND="${@:3}"

echo "Waiting for $SERVICE_NAME to start on port $PORT ..."

while ! nc -z localhost $PORT; do
    echo "Waiting for $SERVICE_NAME to start on port $PORT ..."
    sleep 2
done

echo "$SERVICE_NAME has started on port $PORT. Starting next service ..."
exec $NEXT_COMMAND
