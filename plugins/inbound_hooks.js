const os = require("os");
const fs = require("fs");
const path = require("path");
const util = require("util");
const crypto = require("crypto");

const link = util.promisify(fs.link);
const exists = util.promisify(fs.exists);
const unlink = util.promisify(fs.unlink);
const copy_file = util.promisify(fs.copyFile);

const MAILDIR_BASE = __dirname.replace("plugins", "/maildir");
const MAIL_DOMAINS_FILE = __dirname.replace("plugins", "/config/mail_domains.json");
const MAILBOXES_FILE = __dirname.replace("plugins", "/config/mailboxes.json");


exports.hook_rcpt = function (next, connection, params) {
    const context = this;

    if (connection.relaying) {
        return next(OK); // OK, skip rcpt check for outbound
    }

    let rcpt = params[0];

    if (context.config.get("aliases", "aliases").hasOwnProperty(`${rcpt.user}@${rcpt.host}`)) {
        return next(OK); // OK, alias accepted
    }

    let mail_domains = JSON.parse(fs.readFileSync(MAIL_DOMAINS_FILE, "utf8"));

    if (mail_domains.includes(rcpt.host)) {
        let mailboxes = JSON.parse(fs.readFileSync(MAILBOXES_FILE, "utf8"));

        if (mailboxes.includes(`${rcpt.user}@${rcpt.host}`)) {
            return next(OK); // OK, recipient accepted
        }
    }

    return next(DENY); // DENY, recipient rejected
};

exports.hook_queue = function (next, connection, params) {
    if (connection.relaying) {
        return next(); // OK, skip queueing for outbound
    }

    const context = this;

    const transaction = connection.transaction;
    const message_stream = transaction.message_stream;

    const filename = `${transaction.uuid}.${connection.local.host}`;
    const unique_filename = `${generate_random_string(10)}.${filename}`;
    const tmp_dir = os.tmpdir();
    const tmp_file = path.join(tmp_dir, unique_filename);

    const write_stream = fs.createWriteStream(tmp_file);
    write_stream.write(`Received-At: ${new Date().toISOString()}\r\n`);
    message_stream.pipe(write_stream);

    write_stream.on("error", (error) => handle_error(error, context, next));
    write_stream.on("finish", () => deliver_file_to_rcpts(filename, tmp_file, transaction.rcpt_to, context).then(() => next(OK, "Delivered")).catch(error => handle_error(error, context, next)).finally(() => {
        write_stream.close();
        return try_delete_file(tmp_file);
    }));
}

function handle_error(error, context, next) {
    context.logerror(error.toString());
    return next(DENY, error.toString()); // DENY, reject the mail.
}

function deliver_file_to_rcpts(filename, tmp_file, rcpts, context) {
    return Promise.all(rcpts.map(rcpt => {
        const unique_filename = `${generate_random_string(10)}.${filename}`;
        return deliver_file_to_rcpt(unique_filename, tmp_file, rcpt, context);
    }));
}

function deliver_file_to_rcpt(filename, tmp_file, rcpt, context) {
    const tmp_dir = path.join(MAILDIR_BASE, "tmp");
    const new_dir = path.join(MAILDIR_BASE, "new");
    const tmp_target_file = path.join(tmp_dir, filename);
    const new_target_file = path.join(new_dir, filename);
    const delivered_to_header = `Delivered-To: ${rcpt.user}@${rcpt.host}\r\n`;

    return Promise
        .all([exists(tmp_file), exists(tmp_dir), exists(new_dir)])
        .then(function ([tmp_file_exists, tmp_dir_exists, new_dir_exists]) {
            let msg = null;

            if (!tmp_file_exists) {
                msg = `tmp file does not exist: "${tmp_file}"`;
            } else if (!tmp_dir_exists) {
                msg = "tmp directory does not exist.";
            } else if (!new_dir_exists) {
                msg = "new directory does not exist.";
            }
            if (msg) {
                throw new Error(msg);
            }

            return copy_file(tmp_file, tmp_target_file)
                .then(function () {
                    return prepend_file(tmp_target_file, delivered_to_header);
                })
                .then(function () {
                    return link(tmp_target_file, new_target_file)
                })
                .then(function () {
                    return try_delete_file(tmp_target_file)
                });
        });
}

function prepend_file(file, data) {
    return new Promise((resolve, reject) => {
        fs.readFile(file, "utf8", (err, content) => {
            if (err) {
                reject(err);
                return;
            }

            const updated_content = data + content;

            fs.writeFile(file, updated_content, "utf8", (err) => {
                if (err) {
                    reject(err);
                    return;
                }

                resolve();
            });
        });
    });
}

async function try_delete_file(file) {
    if (await exists(file)) {
        return unlink(file);
    }
}

function generate_random_string(length) {
    return crypto.randomBytes(Math.ceil(length / 2)).toString("hex").slice(0, length).toUpperCase();
}