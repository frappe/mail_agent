const amqp = require("amqplib");
require("dotenv").config({ path: __dirname.replace("plugins", ".env") });

const AGENT_ID = process.env.AGENT_ID;
const RABBITMQ_HOST = process.env.RABBITMQ_HOST;
const RABBITMQ_PORT = process.env.RABBITMQ_PORT;
const RABBITMQ_VIRTUAL_HOST = process.env.RABBITMQ_VIRTUAL_HOST;
const RABBITMQ_USERNAME = process.env.RABBITMQ_USERNAME;
const RABBITMQ_PASSWORD = process.env.RABBITMQ_PASSWORD;
const RABBITMQ_QUEUE = "mail_agent::outgoing_mails_status";
const RABBITMQ_URL = `amqp://${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}@${RABBITMQ_HOST}:${RABBITMQ_PORT}/${RABBITMQ_VIRTUAL_HOST}`;

exports.register = async function () {
    try {
        this.loginfo("Connecting to RabbitMQ...");
        this.rmq_connection = await amqp.connect(RABBITMQ_URL);
        this.rmq_channel = await this.rmq_connection.createChannel();
        await this.rmq_channel.assertQueue(RABBITMQ_QUEUE, {
            durable: true,
            arguments: { "x-max-priority": 3 },
        });
        this.loginfo("RabbitMQ connection and channel established.");
    } catch (error) {
        this.logerror(`Failed to connect to RabbitMQ: ${error.message}`);
        throw error;
    }
};

exports.hook_queue_ok = async function (next, connection) {
    if (!connection.relaying) {
        return next(); // Skip for inbound
    }

    try {
        const queue_id = connection.transaction.uuid;
        const outgoing_mail = connection.transaction.header
            .get("X-FM-OM")
            .replace(/(\r\n|\n|\r)/gm, "");

        connection.transaction.notes.queue_id = queue_id;
        connection.transaction.notes.outgoing_mail = outgoing_mail;

        const data = {
            hook: "queue_ok",
            queue_id: queue_id,
            outgoing_mail: outgoing_mail,
        };

        await enqueue_delivery_status(this.rmq_channel, data);
        this.loginfo(`Queue OK status enqueued for ${queue_id}`);
    } catch (error) {
        this.logerror(`Error processing hook_queue_ok: ${error.message}`);
    }

    return next();
};

exports.hook_deferred = async function (next, hmail, params) {
    try {
        const rcpt_to = hmail.todo.rcpt_to;
        const queue_id = hmail.todo.uuid.replace(/\.\d+$/, "");
        const outgoing_mail = hmail.notes.outgoing_mail;

        const data = {
            rcpt_to: rcpt_to,
            hook: "deferred",
            queue_id: queue_id,
            retries: hmail.num_failures - 1,
            outgoing_mail: outgoing_mail,
            action_at: new Date().toISOString(),
        };

        if (hmail.num_failures <= 3) {
            await enqueue_delivery_status(this.rmq_channel, data);
            this.loginfo(`Deferred status enqueued for ${queue_id}`);
            return next();
        }

        data.hook = "bounce";
        await enqueue_delivery_status(this.rmq_channel, data);
        this.logwarn(`Mail bounced after max retries for ${queue_id}`);
        return next(OK); // OK, drop the mail completely.
    } catch (error) {
        this.logerror(`Error processing hook_deferred: ${error.message}`);
        return next(); // Proceed to next hook regardless of the error
    }
};

exports.hook_bounce = async function (next, hmail, error) {
    try {
        const rcpt_to = hmail.todo.rcpt_to;
        const queue_id = hmail.todo.uuid.replace(/\.\d+$/, "");
        const outgoing_mail = hmail.notes.outgoing_mail;

        const data = {
            hook: "bounce",
            rcpt_to: rcpt_to,
            queue_id: queue_id,
            retries: hmail.num_failures,
            outgoing_mail: outgoing_mail,
            action_at: new Date().toISOString(),
        };

        await enqueue_delivery_status(this.rmq_channel, data);
        this.logwarn(`Bounce status enqueued for ${queue_id}`);
    } catch (error) {
        this.logerror(`Error processing hook_bounce: ${error.message}`);
    }

    return next(OK); // OK, don't send bounce message to the originating sender.
};

exports.hook_delivered = async function (next, hmail, params) {
    try {
        const queue_id = hmail.todo.uuid.replace(/\.\d+$/, "");
        const outgoing_mail = hmail.notes.outgoing_mail;

        const data = {
            params: params,
            hook: "delivered",
            queue_id: queue_id,
            retries: hmail.num_failures,
            outgoing_mail: outgoing_mail,
            action_at: new Date().toISOString(),
        };

        await enqueue_delivery_status(this.rmq_channel, data);
        this.loginfo(`Delivered status enqueued for ${queue_id}`);
    } catch (error) {
        this.logerror(`Error processing hook_delivered: ${error.message}`);
    }

    return next();
};

async function enqueue_delivery_status(channel, data) {
    try {
        await channel.sendToQueue(
            RABBITMQ_QUEUE,
            Buffer.from(JSON.stringify(data)),
            {
                persistent: true,
                appId: AGENT_ID,
            }
        );
    } catch (error) {
        console.error(`Error enqueueing delivery status: ${error.message}`);
        throw error;
    }
}

exports.shutdown = async function () {
    try {
        if (this.rmq_channel) {
            await this.rmq_channel.close();
            this.loginfo("RabbitMQ channel closed.");
        }
        if (this.rmq_connection) {
            await this.rmq_connection.close();
            this.loginfo("RabbitMQ connection closed.");
        }
    } catch (error) {
        this.logerror(`Error during shutdown: ${error.message}`);
    }
};
