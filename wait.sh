#!/bin/bash

SERVICE_NAME=$1
PORT=$2
NEXT_COMMAND="${@:4}"

HOST=${3:-localhost}

echo "Waiting for $SERVICE_NAME to start on $HOST:$PORT ..."

timeout=30
interval=2
elapsed=0

while ! nc -z $HOST $PORT; do
    if [ $elapsed -ge $timeout ]; then
        echo "Error: $SERVICE_NAME did not start on $HOST:$PORT within $timeout seconds."
        exit 1
    fi
    echo "Waiting for $SERVICE_NAME to start on $HOST:$PORT ..."
    sleep $interval
    elapsed=$((elapsed + interval))
done

echo "$SERVICE_NAME has started on $HOST:$PORT. Starting next service ..."
exec $NEXT_COMMAND
