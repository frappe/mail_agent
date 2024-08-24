const os = require("os");
const fs = require("fs");
const path = require("path");
const util = require("util");
const amqp = require("amqplib");
const crypto = require("crypto");
const unlink = util.promisify(fs.unlink);
const readFile = util.promisify(fs.readFile);

const AGENT_ID = process.env.AGENT_ID;
const RABBITMQ_HOST = process.env.RABBITMQ_HOST;
const RABBITMQ_PORT = process.env.RABBITMQ_PORT;
const RABBITMQ_VIRTUAL_HOST = process.env.RABBITMQ_VIRTUAL_HOST;
const RABBITMQ_USERNAME = process.env.RABBITMQ_USERNAME;
const RABBITMQ_PASSWORD = process.env.RABBITMQ_PASSWORD;
const RABBITMQ_QUEUE = "mail_agent::incoming_mails";
const RABBITMQ_URL = `amqp://${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}@${RABBITMQ_HOST}:${RABBITMQ_PORT}/${RABBITMQ_VIRTUAL_HOST}`;

exports.register = async function () {
    try {
        this.loginfo("Connecting to RabbitMQ...");
        this.connection = await amqp.connect(RABBITMQ_URL);
        this.channel = await this.connection.createChannel();
        await this.channel.assertQueue(RABBITMQ_QUEUE, { durable: true });
        this.loginfo("RabbitMQ connection and channel established.");
    } catch (error) {
        this.logerror(`Failed to connect to RabbitMQ: ${error.message}`);
        throw error;
    }
};

exports.hook_rcpt = function (next, connection, params) {
    this.loginfo("Recipient accepted: Catch-All");
    return next(OK);
};

exports.hook_queue = function (next, connection, params) {
    if (connection.relaying) {
        this.loginfo("Skipping queueing for relaying (outbound) connection.");
        return next();
    }

    const transaction = connection.transaction;
    const message_stream = transaction.message_stream;
    const tmp_file = path.join(
        os.tmpdir(),
        `${generate_random_string(10)}.email`
    );

    this.loginfo(`Storing incoming email to temporary file: ${tmp_file}`);

    const write_stream = fs.createWriteStream(tmp_file);
    write_stream.write(`Received-At: ${new Date().toISOString()}\r\n`);
    message_stream.pipe(write_stream);

    write_stream.on("error", (error) => handle_error(error, this, next));
    write_stream.on("finish", async () => {
        try {
            const content = await readFile(tmp_file);
            await process_recipients(transaction, content, this);
            next(OK, "Delivered");
        } catch (error) {
            handle_error(error, this, next);
        } finally {
            write_stream.close();
            await try_delete_file(tmp_file, this);
        }
    });
};

function handle_error(error, context, next) {
    context.logerror(`Error occurred: ${error.toString()}`);
    return next(DENY, "Message rejected due to an internal error.");
}

async function process_recipients(transaction, content, context) {
    const rcpts = transaction.rcpt_to;
    for (const rcpt of rcpts) {
        const delivered_to_header = `Delivered-To: ${rcpt.user}@${rcpt.host}\r\n`;
        const content_with_header = delivered_to_header + content;
        try {
            context.loginfo(
                `Sending message to RabbitMQ for recipient: ${rcpt.user}@${rcpt.host}`
            );
            await context.channel.sendToQueue(
                RABBITMQ_QUEUE,
                Buffer.from(content_with_header),
                {
                    persistent: true,
                    appId: AGENT_ID,
                }
            );
        } catch (error) {
            context.logerror(
                `Failed to send message to RabbitMQ for ${rcpt.user}@${rcpt.host}: ${error.message}`
            );
            throw error;
        }
    }
}

async function try_delete_file(file, context) {
    try {
        await unlink(file);
        context.loginfo(`Temporary file deleted: ${file}`);
    } catch (error) {
        context.logerror(
            `Failed to delete temporary file: ${file} - Error: ${error.message}`
        );
    }
}

function generate_random_string(length) {
    return crypto
        .randomBytes(Math.ceil(length / 2))
        .toString("hex")
        .slice(0, length)
        .toUpperCase();
}

exports.shutdown = async function () {
    try {
        if (this.channel) {
            await this.channel.close();
            this.loginfo("RabbitMQ channel closed.");
        }
        if (this.connection) {
            await this.connection.close();
            this.loginfo("RabbitMQ connection closed.");
        }
    } catch (error) {
        this.logerror(`Error during shutdown: ${error.message}`);
    }
};
