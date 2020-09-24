# Problem description

Very large indexes containing a large variety of data can cause SmartStore churn as sparse searches require small amounts of data from multiple buckets. This can force SmartStore to localize a very large number of buckets, despite only needing a small amount of data from each. 

## Existing Solutions
Currently you can try and use TERM, host, source and sourcetype to improve bucket elimination so that only the `metadata` and `bloomfilter` need to be downloaded from your considered buckets. 

## Proposed Solution
We can attempt to use the new option "splitByIndexKeys" and increase the number of hot buckets so that sharding occurs within the index itself. This will improve bucket elmination when searching on the appropiate metadata fields.

    splitByIndexKeys = <comma separated list>
    * By default, splunkd splits buckets by time ranges with each bucket having its
    earliest and latest time.
    * If one or several keys are provided, splunkd splits buckets by the index key,
    or a combination of the index keys if more than one key is provided. The
    buckets will no longer be split by time ranges.
    * Valid values are: host, sourcetype, source, metric_name
    * This setting only applies to metric indexes.
    * If not set, splunkd splits buckets by time span.
    * Default: empty string (no key)

Although it is stated that this only works for metrics indexes, this is not true.

###  Data

We try and emulate the frequency of events found in a default splunk instance focusing on the `splunkd` sourcetype by looking at the frequency of component logging. We then join this with a concept of "stacks" which are embedded in the host names used in Splunk Cloud. This is documented in the data generation workbook.

### Steps to load

We borrow from the [load data into indexes|../ingest_eval_examples] example to lift the data into events and then use `CLONE_SOURCETYPE` to create fresh events under the sourcetype `shard_data_with_splitbyindexkeys` and throw away the orignal. 

Then we process the fresh new events: 

1. We create an index using `splitByIndexKeys` and increase the number of hot buckets
1. We extract the `component` from the events borrowing from the [Enrich splunkd logging|../enrich_splunkd_component_level_thread] usecase.
1. We extract the metadata from the host name to extract the `stack` name 
1. We assign the value for `component` to the `sourcetype` and the `stack` to the `source`
    1. We reassign the orginal `sourcetype` and `source` to `orig_sourcetype` and `original_source` 
1. Finally we route the event to the index
    1. If the `component` value is not extracted we route to the `detritus`

#### indexes.conf

    [shard_data_with_splitbyindexkeys]
    homePath = $SPLUNK_DB/shard_data_with_splitbyindexkeys/db
    coldPath = $SPLUNK_DB/shard_data_with_splitbyindexkeys/colddb
    thawedPath = $SPLUNK_DB/shard_data_with_splitbyindexkeys/thaweddb
    # we set the size the buckets to be small so they roll more frequently
    maxDataSize=1
    journalCompression = zstd
    tsidxWritingLevel=3
    disabled = 0
    # the more hots buckets the better the sharding
    maxHotBuckets = 20
    # we will shard around source and sourcetype
    splitByIndexKeys=source,sourcetype

#### props.conf

    # This is the process for extracting the meta data from a splunkd event and writting it to the sharded index
    [shard_data_with_splitbyindexkeys]
    TRANSFORMS-shard_data_with_splitbyindexkeys = enrich_splunkd_component_level_thread-extract_log_level_etc, enrich_splunkd_component_level_thread-drop_null_thread_info, shard_data_with_splitbyindexkeys-extract_metadata_from_host, shard_data_with_splitbyindexkeys-move_meta_data
    # we are fully decomposing the URL we don't need MAJOR breakers
    SEGMENTATION=search

#### transforms

    # Use REGEX to extract the values for component, log_level, thread_id and thread_name as indexed fields
    [enrich_splunkd_component_level_thread-extract_log_level_etc]
    SOURCE_KEY = _raw
    WRITE_META = true
    REGEX = ^\d\d\-\d\d-\d{4}\s\d\d:\d\d\:\d\d\.\d{0,6}\s[+\-]\d{4}\s(INFO|DEBUG|ERROR|WARN|DEBUG)\s+(\S+)\s(?:\[(\d+)\s(\S+)\])?
    FORMAT = log_level::$1 component::$2 thread_id::$3 thread_name::$4 

    # the values for thread name and thread_id are optional which will produce empty indexed fields, we use this transform to remove them
    [enrich_splunkd_component_level_thread-drop_null_thread_info]
    INGEST_EVAL = thread_id:=if(thread_id="",null(),thread_id), thread_name:=if(thread_name="",null(),thread_name)

    # we use REGEX to extract the meta data encoded in the host name
    [shard_data_with_splitbyindexkeys-extract_metadata_from_host]
    SOURCE_KEY = MetaData:Host
    WRITE_META = true
    REGEX = ^(?:host::)?([^\-]+)-([^\.]+)+\.([^\.]+)\.(.+)$
    FORMAT = role::"$1" instance::"$2" stack::"$3" domain::"$4"

    # we want to write the component name into to sourcetype field, and stack name into the source field, if the component isn't extracted we send to detritus.
    [shard_data_with_splitbyindexkeys-move_meta_data]
    INGEST_EVAL =  orig_source=source, orig_sourcetype=sourcetype, source=stack, sourcetype=component, index=if(isnull(component), "detritus", index)


