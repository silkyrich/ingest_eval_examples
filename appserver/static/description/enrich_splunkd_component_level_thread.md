# Problem statment
Every Splunk component generates numerous log files including `metrics.log`, `splunkd.log`, `health.log` and more. These log files all share the same sourcetype `splunkd` and this is written to the index `_internal`. This index is normally in the top largest indexes on any Splunk platform and the contents are vital to monitoring and debugging splunk. In later releases `thread_name` and `thread_id` has been added to logging from `splunkd.log`. Because of its size searching the `_internal` index is expensive and slow.

## Existing solution
By default enrichment of the `splunkd` sourcetype is done at search time using schema on the fly. This highly efficent if you are not searching that index as you save parsing costs at point of ingestion. However at point of searching this is expensive and time consuming.

## Proposed Solution
To aid the performance of searching the `splunkd` sourcetype we will use a `REGEX` transform to extract the fields `component`, `log_line`, `thread_name` and `thread_id` from the log files and write them into indexed fields during ingestion. This will increase the parsing costs at ingestion time, but will reduce searching costs when referencing the indexed fields.

### Example data
To demonstrate how `INGEST_EVAL` can resolve the issue this application generates some sample data. Notice how the file name contains the date, but the log file contains the time.

    08:44:00 Splunk> See your world. Maybe wish you hadn’t.


### Steps

1. We start with a `REGEX` extraction to extract the fields `component`, `log_line`, `thread_name` and `thread_id`
1. The fields `thread_name` and `thread_id` are optional which will create empty indexed fields
1. We use INGEST_EVAL to remove the indexed fields `thread_name` and `thread_id` when they were empty

### props.conf

    # this transform applies a REGEX transform to extract the log_level, the component and thread name and if is it there
    [enrich_splunkd_component_level_thread]
    TIME_PREFIX = ^
    TIME_FORMAT = %m-%d-%Y %H:%M:%S.%l %z
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-enrich-splunkd-log_level = enrich_splunkd_component_level_thread-extract_log_level_etc, enrich_splunkd_component_level_thread-drop_null_thread_info

### transforms.conf

    [enrich_splunkd_component_level_thread-extract_log_level_etc]
    SOURCE_KEY = _raw
    WRITE_META = true
    REGEX = ^\d\d\-\d\d-\d{4}\s\d\d:\d\d\:\d\d\.\d{0,6}\s\+|-\d{4}\s(INFO|DEBUG|ERROR|WARN|DEBUG)\s+(\S+)\s(?:\[(\d+)\s(\S+)\])?
    FORMAT = log_level::$1 component::$2 thread_id::$3 thread_name::$4 

    [enrich_splunkd_component_level_thread-drop_null_thread_info]
    INGEST_EVAL = thread_id:=if(thread_id="",null(),thread_id), thread_name:=if(thread_name="",null(),thread_name)
    
