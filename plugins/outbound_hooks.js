const amqp = require("amqplib");
require("dotenv").config({ path: __dirname.replace("plugins", ".env") });

const RABBITMQ_HOST = process.env.RABBITMQ_HOST;
const RABBITMQ_PORT = process.env.RABBITMQ_PORT;
const RABBITMQ_USERNAME = process.env.RABBITMQ_USERNAME;
const RABBITMQ_PASSWORD = process.env.RABBITMQ_PASSWORD;
const RABBITMQ_QUEUE = "mail_agent::outgoing_mails_status";
const RABBITMQ_URL = `amqp://${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}@${RABBITMQ_HOST}:${RABBITMQ_PORT}`;

exports.register = async function () {
    this.connection = await amqp.connect(RABBITMQ_URL);
    this.channel = await this.connection.createChannel();
    await this.channel.assertQueue(RABBITMQ_QUEUE, {
        durable: true,
        arguments: { "x-max-priority": 3 },
    });
};

exports.hook_queue_ok = async function (next, connection) {
    if (!connection.relaying) {
        return next(); // OK, skip for inbound
    }

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
    await enqueue_delivery_status(this.channel, data);

    return next();
};

exports.hook_deferred = async function (next, hmail, params) {
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
        await enqueue_delivery_status(this.channel, data);
        return next();
    }

    data.hook = "bounce";
    await enqueue_delivery_status(this.channel, data);

    return next(OK); // OK, drop the mail completely.
};

exports.hook_bounce = async function (next, hmail, error) {
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
    await enqueue_delivery_status(this.channel, data);

    return next(OK); // OK, don't send bounce message to the originating sender.
};

exports.hook_delivered = async function (next, hmail, params) {
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
    await enqueue_delivery_status(this.channel, data);

    return next();
};

async function enqueue_delivery_status(channel, data) {
    await channel.sendToQueue(RABBITMQ_QUEUE, Buffer.from(JSON.stringify(data)), {
        persistent: true,
    });
}
