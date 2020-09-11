# Problem description

Indexed fields are a key accelaration technlogy and can are used with `tstats` to provide a more SQL like search expirence. These searches avoid the need to access the `_raw` data from the journal file. This saves downloading the journal, the extraction and decompression of slices, and avoids schema on the fly - these savings are significant and can be more than 40 times faster. However it can be time consuming and difficult to get indexed fields into your data. 

Some file format conform to a consistent naming convension where attributes are assigned to values. This can be seen in splunkd's metrics.log file.

#### Example log line from metrics.log

    01-27-2020 20:29:22.922 +0000 INFO Metrics - group=per_sourcetype_thruput, ingest_pipe=0, series="splunkd", kbps=258.6201534528208, eps=1367.6474892210738, kb=8050.1142578125, ev=42571, avg_age=145747.7853938127, max_age=2116525


We would like to create indexed fields for each of the attribute names: `group`, `ingest_pipe`, `series` ... etc ... and assign those attribtes their associated values `per_sourcetype_thruput`, `0`, `splunkd` ... etc ...

With this done we can write high performance `tstats` searches like:

    | tstats p95(kbps) where index=_internal TERM(Metrics) and group=per_sourcetype_thruput by _time span=1hr


## Existing solution

There are various ways to insert indexed fields into your ingdex, the most common are documented here. But there exist no out of the box solution for this use case.

* [Create custom fields at index time](https://docs.splunk.com/Documentation/Splunk/latest/Data/Configureindex-timefieldextraction)
* [Format events for HTTP Event Collector](https://docs.splunk.com/Documentation/Splunk/latest/Data/FormateventsforHTTPEventCollector)
* [Extract fields from files with structured data](https://docs.splunk.com/Documentation/Splunk/latest/Data/Extractfieldsfromfileswithstructureddata)

This solution is based on the features described in the first bullet.

## Proposed Solution

We can use a series of REGEX transformations to extract the values and attributes from the log file and then use the `META_ADD=true` option to append the indexed fields to the `_meta` field. This solution cannot be implemented in `INGEST_EVAL`.

### Sample data

This application creates a log file for us to test and apply the method to.

#### indexed.log

    2020-08-28 23:09:18 name='single quotes' sum_kbps=8334
    2020-08-28 23:13:18 group="double quotes" sum_kbps=3051 stdev_kbps=0.03767104255809539
    2020-08-28 23:15:57 name=no_quotes sum_kbps=9560
    2020-08-28 23:35:13 stdev_kbps=0.0054915638140592415 value=1429
    2020-08-28 23:37:20 label="double quotes" group=no_quotes stdev_kbps=0.9375614115100175 name='single quotes'
    2020-08-28 23:39:08 stdev_kbps=0.14575641669994088 label="double quotes" value=313 average_kbps=0.1644034931497017 name="double quotes"
    2020-08-28 23:40:32 group="double quotes" sum_kbps=8684 average_kbps=0.05122808844009563 stdev_kbps=0.07653246808729353
    2020-08-29 00:00:01 average_kbps=0.7319356429044452 stdev_kbps=0.06484472283154874
    2020-08-29 00:19:29 sum_kbps=6609 stdev_kbps=0.7860664557421805
    2020-08-29 00:29:17 average_kbps=0.10549943657388261 sum_kbps=4382
    2020-08-29 00:33:05 label="double quotes" sum_kbps=4560
    2020-08-29 01:05:14 stdev_kbps=0.5248050365656354 value=460 label='single quotes' average_kbps=0.6813920691093273
    2020-08-29 01:43:46 name=no_quotes sum_kbps=3237 value=6946 stdev_kbps=0.7316282693378682
    2020-08-29 02:09:13 name=no_quotes stdev_kbps=0.6549719038966627
    2020-08-29 03:02:43 sum_kbps=4347 group='single quotes'

### Steps

1. Extract time and line break as normal
1. Disable `MAJOR_BREAKERS` by using the `segmentation=search` option to save space
1. Apply the regex to extract attribute value pairs in the form `attribute=value`
    1. Append `attribute::"value"` to `_meta`
    1. Repeat the match until EOL
1. Apply the regex to extract attribute value pairs in the form `attribute="value"`
    1. Append `attribute::"value"` to `_meta`
    1. Repeat the match until EOL
1. Apply the regex to extract attribute value pairs in the form `attribute='value'`
    1. Append `attribute::"value"` to `_meta`
    1. Repeat the match until EOL

### props.conf

    # This sourcetype is an example for how we can use REPEAT_MATCH and regex to automatically extract fields from log files
    [indexed_log]
    TIME_PREFIX = ^
    TIME_FORMAT = %Y-%m-%d %H:%M:%S
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-extract_indexed_fields=regex_extract_doubled_quoted_av_pairs, regex_extract_single_quoted_av_pairs, regex_extract_unquoted_av_pairs


### transforms.conf

    # this regex finds single quoted attribute value pairs, ie the form a=b, and appends them to _meta
    [regex_extract_unquoted_av_pairs]
    SOURCE_KEY = _raw
    REGEX = \s([a-zA-Z][a-zA-Z0-9_-]+)=([^\s"',]+)
    REPEAT_MATCH=true
    FORMAT = $1::"$2"
    WRITE_META = true

    # this regex finds single quoted attribute value pairs, ie the form a='b', and appends them to _meta
    [regex_extract_single_quoted_av_pairs]
    SOURCE_KEY = _raw
    REGEX = \s([a-zA-Z0-9_-]+)='([^']+)'
    REPEAT_MATCH=true
    FORMAT = $1::"$2"
    WRITE_META = true

    # this regex finds single quoted attribute value pairs, ie the form a="b", and appends them to _meta
    [regex_extract_doubled_quoted_av_pairs]
    SOURCE_KEY = _raw
    REGEX = \s([a-zA-Z][a-zA-Z0-9_-]+)="([^"]+)"
    REPEAT_MATCH=true
    FORMAT = $1::"$2" 
    WRITE_META = true
