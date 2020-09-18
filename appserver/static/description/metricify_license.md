# Problem description

Running searches to compute license usgae is very expensive as license.log is held as _raw strings. We must fully parse each log line to access the value for bytes "b" and extract the values for host, sourcetype, instance extra at point of search. This makes it difficult to do deep history analysis on license usage.

## Existing Solutions
Primarily you must search the license log file with `_raw` search and wait

## Proposed Solution
We will copy the events from license_usage.log so that they are also stored in the `_metrics` index so that they can be processed using the `mstats` command.

###  Example log line

    09-18-2020 10:02:11.793 +0100 INFO  LicenseUsage - type=Usage s="my_host" st="m_sourcetype" h="my_host" o="" idx="default" i="18F9C3EA-EBB2-497C-801A-098D0C52F9E2" pool="auto_generated_pool_enterprise" b=2034451 poolsz=53687091200

* `s` : the source that used license
* `st` : the sourcetype that used license
* `h` : the host that used license
* `i` : the GUID of the indexer that reported the license_usgae
* `idx` : the index the data was written to
* `pool` : the name of the license pool
* `b` : the number of bytes written for the `source`, `host` and `sourcetype` on the `indexer` into the `index`
* `poolz` : the total pool_size

#### Back filling data

To back fill your existing data into `_metrics` you use `oneshot` to reload the data and target the `metricify_license` sourcetype

    /Applications/Splunk/bin/splunk nom on -auth admin:password /Applications/Splunk/var/log/splunk/license_usage.log  -sourcetype metricify_license -index main


### The steps performed to process data

1. We intercept the events created by the license_usage.log file using a source specific stanza
1. We use a transform that calls CLONE_SOURCETYPE to create a new event with a new sourcetype `metricify_license`
1. We let the orignal event countinue to indexed as per normal and be written to `the _internal` index
1. We intercept the cloned event by its sourcetype `metricify_license` 
1. We then process the cloned event with a `REGEX` transform and to turn it into a metrics compliant event
    1. We assign a fixed value to `metric_name` and copy extract value for "b" and copy it into `_value` 
    1. We extract the other fields assigning them to more descriptive indexed fields names - these become dimensions
1. We route all other types other than "usage
1. We copy the indexed fields for host, source and sourcetype in to the proper metrics fields
1. Finally we assign the `index` field to `_metrics` steering the event into the metrics index

#### props.conf

    # license usage data is under the splunkd sourcetype, so we need to match on the source file to be more selective 
    # The transform uses CLONE_SOURCETYPE to create a copy of the event for further processing
    [source::.../var/log/splunk/license_usage.log(.\d+)?]
    TRANSFORMS-clone_license = metricify_license-clone

    # These transforms convert the event into a metrics compliant one, and steer to the _metrics index 
    [metricify_license]
    TRANSFORMS-clone_and_convert = metricify_license-extract_fields, shared-drop_useless_time_fields, metricify_license-reassign_meta_fields_and_route_to_index

#### transforms.conf

    # create a copy of the license log files, we leave the orginal event to be written into the _internal index as normal
    [metricify_license-clone]
    REGEX = .
    CLONE_SOURCETYPE = metricify_license
    FORMAT = $0
    DEST_KEY = _raw

    # We use a REGEX transformation to lift the fields and then write them to indexed fields, the value for b becomes _value which is the 
    # metric value, the remaining fields will become dimensions, we hard code the metric name to become license_usage
    # we create two mutally exclusive capture groups for each field that may or may not be quoted with strings, and assign both to the indexed field 
    [metricify_license-extract_fields]
    SOURCE_KEY = _raw
    REGEX = type=(\S+)\ss=(?:"([^"]*)"|(\S*))\s+st=(?:"([^"]+)"|(\S+))\s+h=(?:"([^"]+)"|(\S+))\so="[^"]*"\sidx=(?:"([^"]+)"|(\S+))\si="([^"]+)"\spool="([^"]+)"\sb=(\d+)\spoolsz=(\d+)
    FORMAT = metric_name::"license_usage" type::"$1" from_source::"$2$3" from_sourcetype::"$4$5" from_host::"$6$7" into_index::"$8$9" on_indexer::"$10" allocated_to_pool::"$11" _value::"$12" pool_size::"$13"
    WRITE_META = true

    # We keep data when type=usage, copy the metadata into the proper fields, drop the immediate indexed fields, and then route the metrics data into the _metrics index
    [metricify_license-reassign_meta_fields_and_route_to_index]
    INGEST_EVAL = queue=if(type="Usage", queue, "nullQueue"), host=from_host, sourcetype=from_sourcetype, source=from_source,  type:=null(), from_host:=null(), from_sourcetype:=null(), from_source:=null(), index:="_metrics"





