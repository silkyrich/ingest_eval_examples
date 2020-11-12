# Problem description

Some applications, such as [Docker](https://docs.docker.com/config/containers/logging/json-file/), use JSON object wrappers to encode log events. This can be problematic for Splunk which does not natively recognise the JSON loging format. These applications can typically be configured to generate ordinary logs but most frequently they are left on the default setting and the file monitored.

#### Example log line from docker

[Source](https://docs.docker.com/config/containers/logging/json-file/)

    {"log":"Log line is here\n","stream":"stdout","time":"2019-01-01T11:11:11.111111111Z"}

## Existing Solutions

It is very common for [FluentD](https://docs.fluentd.org/v/0.12/output/splunk)) to be used to read, enrich and convert the JSON log data to a more Splunk friendly format. Alternatively the data can be ingested as a simple `_raw` with JSON encoding which leads to unnecessary passing at search time. Reading JSON log files as `INDEXED_EXTRACTIONS=JSON` does not work as the log string is written to the `TSIDX` as a user defined indexed field. 

## Proposed Solution
We will use `INDEXED_EXTRACTIONS=JSON`to read the file and then use `INGEST_EVAL` to reassign the `log` field to `_raw` and drop the `time` indexed field. This process removes the JSON wrapper and restores the log file its simplest format ideal for ingestion by Splunk. 

It is important to note that the Splunk to Splunk (s2s) transport protocol sends data as parsed or unparsed. Typically data is send from a universal forwarder as unparsed and it comes parsed when it flows through a heavy forwarder or indexer pipeline. You are able to force the indexer or heavy forwarder to reparse the data by forcing data back into the typing queue.

    [splunktcp]
    route = [has_key|absent_key:<key>:<queueName>;...]
    * Settings for the light forwarder.
    * The receiver sets these parameters automatically -- you do not need to set
    them yourself.
    * The property route is composed of rules delimited by ';' (semicolon).
    * The receiver checks each incoming data payload through the cooked TCP port
    against the route rules.
    * If a matching rule is found, the receiver sends the payload to the specified
    <queueName>.
    * If no matching rule is found, the receiver sends the payload to the default
    queue specified by any queue= for this stanza. If no queue= key is set in
    the stanza or globally, the receiver sends the events to the parsingQueue.


When structurd parsing (i.e. `INDEXED_EXTRACTIONS`) is enabled on a universal forwarder the default behaviour changes and the universal forwarder produces parsed data for this source. This means that any processing should be done done locally on the universal forwarder by forcing data to processed locally.

    force_local_processing = <boolean>
    * Forces a universal forwarder to process all data tagged with this sourcetype
    locally before forwarding it to the indexers.
    * Data with this sourcetype is processed by the linebreaker,
    aggerator, and the regexreplacement processors in addition to the existing
    utf8 processor.
    * Note that switching this property potentially increases the cpu
    and memory consumption of the forwarder.
    * Applicable only on a universal forwarder.
    * Default: false

### Steps

1. Set props to load data with `INDEXED_EXTRACTIONS=CSV`
    1. (Optional) Enable `force_local_processing=true` so `INGEST_EVAL` will be evaluted on a universal forwarder
1. Extract the time from the `time` field
1. Reassign the `log` field to the `_raw` field
1. Drop the `log` and `time` fields as they are no longer required
1. Other fields automatically flow through as indexed fields, for instance in this example is the `stream` field

### props.conf

    # json docker messages embedd the log line as a field
    [json_docker]
    # We will use the JSON parser to decompose the JSON structure into indexed fields
    INDEXED_EXTRACTIONS = JSON
    # The value for time is store in the time field
    TIMESTAMP_FIELDS = time
    TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%QZ
    # Use INGEST_EVAL to reassign the fields and replace the _raw string
    TRANSFORMS-json_docker = json_docker_reassign_raw_drop_time

### transforms.conf

    # reassign the log field to the _raw string which removes the json object wrapper, drop the time and log field
    [json_docker_reassign_raw_drop_time]
    INGEST_EVAL = _raw=log, time:=null(), log:=null() 


