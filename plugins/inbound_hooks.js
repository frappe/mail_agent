const os = require("os");
const fs = require("fs");
const path = require("path");
const util = require("util");
const amqp = require("amqplib");
const crypto = require("crypto");
const unlink = util.promisify(fs.unlink);
const readFile = util.promisify(fs.readFile);
require("dotenv").config({ path: __dirname.replace("plugins", ".env") });

const RABBITMQ_HOST = process.env.RABBITMQ_HOST;
const RABBITMQ_PORT = process.env.RABBITMQ_PORT;
const RABBITMQ_USERNAME = process.env.RABBITMQ_USERNAME;
const RABBITMQ_PASSWORD = process.env.RABBITMQ_PASSWORD;
const RABBITMQ_QUEUE = "mail_agent::incoming_mails";
const RABBITMQ_URL = `amqp://${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}@${RABBITMQ_HOST}:${RABBITMQ_PORT}`;

exports.register = async function () {
    this.connection = await amqp.connect(RABBITMQ_URL);
    this.channel = await this.connection.createChannel();
    await this.channel.assertQueue(RABBITMQ_QUEUE, { durable: true });
};

exports.hook_rcpt = function (next, connection, params) {
    return next(OK); // OK, recipient accepted (Catch-All).
};

exports.hook_queue = function (next, connection, params) {
    if (connection.relaying) {
        return next(); // OK, skip queueing for outbound
    }

    const context = this;
    const transaction = connection.transaction;
    const message_stream = transaction.message_stream;
    const tmp_file = path.join(
        os.tmpdir(),
        `${generate_random_string(10)}.email`
    );

    const write_stream = fs.createWriteStream(tmp_file);
    write_stream.write(`Received-At: ${new Date().toISOString()}\r\n`);
    message_stream.pipe(write_stream);

    write_stream.on("error", (error) => handle_error(error, context, next));
    write_stream.on("finish", () => {
        readFile(tmp_file)
            .then((content) => process_recipients(transaction, content, context))
            .then(() => next(OK, "Delivered"))
            .catch((error) => handle_error(error, context, next))
            .finally(() => {
                write_stream.close();
                return try_delete_file(tmp_file);
            });
    });
};

function handle_error(error, context, next) {
    context.logerror(error.toString());
    return next(DENY, error.toString()); // DENY, reject the mail.
}

async function process_recipients(transaction, content, context) {
    const rcpts = transaction.rcpt_to;
    for (const rcpt of rcpts) {
        const delivered_to_header = `Delivered-To: ${rcpt.user}@${rcpt.host}\r\n`;
        const content_with_header = delivered_to_header + content;
        await context.channel.sendToQueue(
            RABBITMQ_QUEUE,
            Buffer.from(content_with_header),
            { persistent: true }
        );
    }
}

async function try_delete_file(file) {
    if (
        await fs.promises
            .access(file)
            .then(() => true)
            .catch(() => false)
    ) {
        return unlink(file);
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
    if (this.channel) {
        await this.channel.close();
    }
    if (this.connection) {
        await this.connection.close();
    }
};