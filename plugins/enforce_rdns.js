const dns = require("dns");

exports.register = function () {
    this.register_hook("lookup_rdns", "lookup_rdns");
};

exports.lookup_rdns = function (next, connection) {
    const remote_ip = connection.remote_ip;
    const message = "The IP address sending this message does not have a PTR record setup, or the corresponding forward DNS entry does not match the sending IP. We do not accept messages from IPs with missing PTR records.";

    if (!remote_ip) {
        return next(DENY, message);
    }

    dns.reverse(remote_ip, (err, hostnames) => {
        if (err || !hostnames || hostnames.length === 0) {
            return next(DENY, message);
        }

        const remote_host = hostnames[0];

        dns.lookup(remote_host, { all: true }, (err, addresses) => {
            if (err || !addresses || addresses.length === 0) {
                return next(DENY, message);
            }

            const matched = addresses.some((addr) => addr.address === remote_ip);

            if (matched) {
                return next();
            } else {
                return next(DENY, message);
            }
        });
    });
};
