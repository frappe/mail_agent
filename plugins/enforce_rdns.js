const dns = require("dns");

exports.register = function () {
    this.loginfo("Registering lookup_rdns hook...");
    this.register_hook("lookup_rdns", "lookup_rdns");
};

exports.lookup_rdns = function (next, connection) {
    const remote_ip = connection.remote.ip;
    const message =
        "The IP address sending this message does not have a PTR record setup, or the corresponding forward DNS entry does not match the sending IP. We do not accept messages from IPs with missing PTR records.";

    this.loginfo(`Processing rDNS lookup for IP: ${remote_ip}`);

    if (!remote_ip) {
        this.logerror("No remote IP found in connection object.");
        return next(DENY, message);
    }

    // Perform reverse DNS lookup
    dns.reverse(remote_ip, (err, hostnames) => {
        if (err) {
            this.logerror(
                `DNS reverse lookup failed for IP: ${remote_ip} - Error: ${err.message}`
            );
            return next(DENY, message);
        }

        if (!hostnames || hostnames.length === 0) {
            this.logerror(`No PTR record found for IP: ${remote_ip}`);
            return next(DENY, message);
        }

        const remote_host = hostnames[0];
        this.loginfo(`PTR record found: ${remote_host} for IP: ${remote_ip}`);

        // Perform forward DNS lookup to verify the PTR record
        dns.lookup(remote_host, { all: true }, (err, addresses) => {
            if (err) {
                this.logerror(
                    `DNS lookup failed for hostname: ${remote_host} - Error: ${err.message}`
                );
                return next(DENY, message);
            }

            if (!addresses || addresses.length === 0) {
                this.logerror(
                    `No forward DNS entries found for hostname: ${remote_host}`
                );
                return next(DENY, message);
            }

            const matched = addresses.some((addr) => addr.address === remote_ip);

            if (matched) {
                this.loginfo(`Forward DNS matches the remote IP: ${remote_ip}`);
                return next();
            } else {
                this.logerror(`Forward DNS does not match the remote IP: ${remote_ip}`);
                return next(DENY, message);
            }
        });
    });
};
