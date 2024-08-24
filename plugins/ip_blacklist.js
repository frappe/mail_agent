const axios = require("axios");

const FRAPPE_BLACKLIST_HOST = process.env.FRAPPE_BLACKLIST_HOST;

exports.hook_connect = async function (next, connection) {
    const remote_ip = connection.remote.ip;

    this.loginfo(`Checking blacklist status for IP: ${remote_ip}`);

    try {
        const response = await axios.get(
            `${FRAPPE_BLACKLIST_HOST}/api/method/mail.api.blacklist.get`,
            {
                params: { ip_address: remote_ip },
                timeout: 5000,
            }
        );

        const data = response.data;
        if (data && data.message) {
            const result = data.message;
            if (result && result.is_blacklisted) {
                this.logwarn(`IP address ${remote_ip} is blacklisted.`);
                return next(
                    DENY,
                    `Connection denied. Your IP address (${remote_ip}) is listed on our blacklist. This could be due to suspected malicious activity or a history of spam. If you believe this is an error, please contact our support team for further assistance.`
                );
            } else {
                this.loginfo(`IP address ${remote_ip} is not blacklisted.`);
            }
        } else {
            this.logerror(
                `Unexpected response format from blacklist API for IP: ${remote_ip}`
            );
        }
    } catch (error) {
        if (error.code === "ECONNABORTED") {
            this.logerror(
                `Request to blacklist API timed out for IP: ${remote_ip} - ${error.message}`
            );
        } else {
            this.logerror(
                `Error calling blacklist API for IP: ${remote_ip} - ${error.message}`
            );
        }
    }

    return next();
};
