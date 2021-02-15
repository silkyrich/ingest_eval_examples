# Problem statement

Searching for IP addresses in Splunk is super expensive due to how the indexing process works. Specifically when a user searches for `index=something dest=10.20.30.1` the platform generates a LISPY `[ AND 1 10 20 30 index::something ]` which matches any event containing `1`, `10`, `20`, `30` and then relies on schema on the fly to sure they are in sequence and in the right order. This elimination after schema on the fly is very wasteful and early elimination at the lexicon stage would return huge dividends.

## Proposed Solution

We use REGEX to extract things that appear to be ip address and write them into an indexed field. We can then modify our searches to use that indexed field for accelaration.

For example we take our search `index=something 10.20.30.1` and add the reference to the indexed field `index=something ip::10.20.30.1 dest=10.20.30.1`. This changes the LISPY so that it includes the indexed field `[ AND 1 10 20 30 index::something ip::10.20.30.1 ]` which then eliminates events that contain `1`, `10`, `20`, `30` but are not IP addresses, for example `1/30/20 value=10` saving the extraction and parsing of a large number of events.

### Sample data

This application creates a log file for us to test and apply the method to. We include obvious invalid IP addresses so that we can try to exclude them.

#### `may_contain_ips`

    05-01-2021 13:28:25 dest=166.138.75.176.208.89 130.237.248.205 259.225.273.220 dest=253.248.199.201
    05-01-2021 13:28:28 dest=21.162.239.136
    05-01-2021 13:28:32 ip=166.244.219.272 dest=140.219.264.132 http://120.240.249.253 dest=237.166.265.220
    05-01-2021 13:28:50 http://130.134.137.208 dest=210.193.249.255 68.160.245.176 http://209.230.87.220
    05-01-2021 13:29:21 dest=249.173.68.216 dest=189.218.100.173
    05-01-2021 13:29:26 ip=160.209.136.145 http://149.128.151.220 http://222.275.97.164 237.133.70.70
    05-01-2021 13:30:22 dest=176.258.189 ip=254.187.179.224 ip=282.169.196.97
    05-01-2021 13:30:31 dest=119.256.131.127
    05-01-2021 13:30:34 102.135.145.44 http://228.283.253.223
    05-01-2021 13:31:17 ip=234.239.274.174 dest=259.54.244.177 162.233.252.253 dest=62.223.206.202
    05-01-2021 13:31:40 78.270.257.241 170.252.235.57.171
    05-01-2021 13:31:49 258.233.25.170 134.106.222.252 ip=56.101.122.201 http://234.206.197.58
    05-01-2021 13:32:10 http://154.197.182.183 ip=146.279.182.192 dest=219.167.258.212 242.235.130.83

Note that from the above we have some invalid ip addresses, examples:

* `282.169.196.97` the first octet is greater than 254
* `166.138.75.176.208.89` is too long

To reject these we need to fine tune the regular expressions to exclude them. The following configuration only matches a single sourcetype, but it could be applied to all events

### props.conf

    # scan the raw string to extract anything that conforms to an IP address format and write it out as a indexed field
    [find_ip_addresses]
    TIME_FORMAT = %d-%m-%Y %H:%M:%S
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-find-find_ip_addresses=find_ip_addresses


### transforms.conf

    # Use a complex regex to auto detect number strings that conform to an ip address, note that the regex uses look a head and look behind to throw out ip addresses
    [find_ip_addresses]
    REGEX = (?<![\d\.])((?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))(?![\d\.])
    SOURCE_KEY = _raw
    REPEAT_MATCH=true
    FORMAT = ip::"$1"
    WRITE_META = true

