# Problem description

Occasionally you may want to export sample data from a production and import it to another. This is especially true when you wish to develop custom props and transforms for enriching data. 

## Existing Solutions
Primarily you need access to the orignal log files or be able intercept and fork the incoming stream.

## Proposed Solution
We write a search that encodes the basic data, `host`, `_raw`, `sourcetype` and `source` into a CSV which can be exported from any splunk instance via search and create a sourcetype which can break up the CSV and write the values back into the appropiate fields


### User steps

1. Run the search to capture the sample of data that you require
1. Export the table as a CSV and export via download in your browser
1. Use oneshot to load data into splunk specifying the import sourcetype

    /Applications/Splunk/bin/splunk nom on -auth admin:password /Applications/Splunk/etc/apps/ingest_eval_examples/sample/import_data  -sourcetype import_data 


### The steps performed to import data

1. Break on the line end ^^^END^^^ 
1. Strip the double quotes with SED_CMD, this undoes the splunk encoding of quotes
1. Read the epoch time stamp from the start of the file
1. Use a REGEX transform to extract the components for `index`, `host`, `source` and `sourcetype`, write to temporay indexed fields
1. Use INGEST_EVAL to copy the temporay indexed fields to the correct metadata files
1. Use INGEST_EVAL and replace to strip the "header" from the _raw field

### The search to export data follows:
This search finds all data recieved in a one hour period, sampled at one event in every ten and writes the result to a table

    index IN (ingest_eval_examples_1, ingest_eval_examples_2) _index_earliest=-15m _index_latest=now earliest=-1y latest=+1y
    | noop sample_ratio=10 
    | eval _raw=_time."%%%".index."%%%".host."%%%".sourcetype."%%%".sourcetype."%%%"._raw."^^^END^^^"
    | table _raw

### props.conf

    # this is an example for importing data from an external splunk instance
    [import_data]
    # time is stored in epoch at the start of each line
    TIME_FORMAT = %s.%3Q
    TIME_PREFIX = ^
    # the transform required to drop the header extract the metafields and copy to the correct fields
    TRANSFORMS-extract-metadata = drop_header, extract_metadata_copy_to_meta, reassign_meta_to_metadata, remove_metadata_from_raw
    # Splunk uses double quotes to escape quotes, we want to remove this before we start extracting the fields
    SEDCMD-strip_double_quotes= s/""/"/g
    # The solution supports multiline events
    LINE_BREAKER=(\^\^\^END\^\^\^"\n)
    SHOULD_LINEMERGE=false

### transforms.conf

    # the header field form a Splunk CSV export starts with the first row being named after the header _raw. We want to drop these
    [drop_header]
    INGEST_EVAL = queue=if(_raw="\"_raw\"","nullQueue", queue)

    # We use REGEX to pop out the values for index, host, sourcetype & source, we then write them to tempory variables in _meta.
    # We assume that % is not found in the primary keys to optimize the REGEX
    [extract_metadata_copy_to_meta]
    SOURCE_KEY=_raw
    WRITE_META = true
    REGEX = ^"\d+(?:\.\d+)?%%%([^%]+)%%%([^%]+)%%%([^%]+)%%%([^%]+)%%%
    FORMAT = my_index::"$1" my_host::"$2" my_source::"$3" my_sourcetype::"$4"

    # copy the temporary user defined fields into the primary metadata locations and then delete the temporary fields
    [reassign_meta_to_metadata]
    INGEST_EVAL = host:=my_host, source:=my_source, index:=my_index, sourcetype:=my_sourcetype, my_host:=null(), my_source=null(), my_index:=null(), my_sourcetype:=null()

    # extract the _raw field from the protocol and write back to _raw
    [remove_metadata_from_raw]
    INGEST_EVAL = _raw=replace(_raw, "^[^%]+%%%(?:[^%]+)%%%(?:[^%]+)%%%(?:[^%]+)%%%(?:[^%]+)%%%(.*)","\1")
