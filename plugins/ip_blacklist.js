const axios = require("axios");
require("dotenv").config({ path: __dirname.replace("plugins", ".env") });

const FRAPPE_BLACKLIST_HOST = process.env.FRAPPE_BLACKLIST_HOST;

exports.hook_connect = async function (next, connection) {
    const remote_ip = connection.remote.ip;

    try {
        const response = await axios.get(`${FRAPPE_BLACKLIST_HOST}/api/method/mail.api.blacklist.get`, {
            params: { ip_address: remote_ip },
            timeout: 5000
        });

        const data = response.data;
        if (data && data.message) {
            const result = data.message;
            if (result && result.is_blacklisted) {
                return next(
                    DENY,
                    `Connection denied. Your IP address (${remote_ip}) is listed on our blacklist. This could be due to suspected malicious activity or a history of spam. If you believe this is an error, please contact our support team for further assistance.`
                );
            }
        }
    } catch (error) {
        if (error.code === "ECONNABORTED") {
            console.error(`Request to blacklist API timed out: ${error.message}`);
        } else {
            console.error(`Error calling blacklist API: ${error.message}`);
        }
    }

    return next();
};
