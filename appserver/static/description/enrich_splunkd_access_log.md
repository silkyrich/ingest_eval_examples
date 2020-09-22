# Problem statement

RESTful calls to splunkd are recorded in `splunkd_access.log`. There is vast number of these and it is very expensive to search as everything is extracted at search time. This is a pity as they track many important interactions and the delay in response is very valuable to understand how efficently splunkd is executing.

## Existing solution

Currently we use schema on the fly and performance is poor, it is expensive to search for delays per rest endpoint. 

## Proposed solution

Fully parse out all the meta data from the log line building out indexed fields. This will allow us to do tstats searches on the duration of the call by rest endpoint and analysis the parameters passed.

### Example log line 

    127.0.0.1 - admin [21/Sep/2020:08:13:51.673 -0030] "GET /servicesNS/nobody/splunk_app_addon-builder/storage/collections/config/?count=-1&offset=0&search=splunk_app_addon-builder HTTP/1.1" 200 30503 - - - 8ms
    10.0.44.11 - hulk@greenmachine.com [21/Sep/2020:08:17:15.312 -0000] "GET /servicesNS/nobody/search/hulk@greenmachine.com/tcpout-server/_reload HTTP/1.0" 200 1955 - - - 15ms

## Steps

1. Use a REGEX transform to extract all the fields and write them to meta. 
    1. Do not attempt to decompose the URL at this point
1. Stash the value for `host` into an tempoary indexed field `my_host` so that we can use `Meta:Host` use with a REGEX transform
1. Decompose the URL around the `?` to extract the `base_url` and the `parmeters`
    1. Copy the parameters to the `host` field
1. Use REGEX with `REPEAT_MATCH` to break up the parameters and copy them to `_meta` with the prefix `rest_param_`
1. Copy the `my_host` value back to its proper location `Meta:Host`
1. Drop the `full_url` and `my_host` fields along with the useless time data

#### props.conf

    # During loading we would like to use REGEX to extract the URL metadata from splunkd_access.log 
    [enrich_splunkd_access_log]
    TIME_PREFIX = \[
    TIME_FORMAT = %d/%b/%Y:%H:%M:%S.%f %z
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-enrich_splunkd_access_log = enrich_splunkd_access_log-decompose_url, enrich_splunkd_access_log-move_host_to_meta, enrich_splunkd_access_log-move_url_to_host, enrich_splunkd_access_log-extract_url_parameters_from_host_to_meta, enrich_splunkd_access_log-meta_copy_back, shared-drop_useless_time_fields 
    # we are fully decomposing the URL we don't need MAJOR breakers
    SEGMENTATION=search


#### trasforms.conf

    # We cannot target _meta with a REGEX transform, so we will copy the URL into the host field
    # This means we must stash the existing host field as an indexed field until we are done
    # We then apply the split function to the full URL to break around the ? REST delimiter 
    # We copy the MV paramaters field into the host field so we can use REGEX repeat match
    [enrich_splunkd_access_log-move_url_to_host]
    INGEST_EVAL = my_host:=host, base_url:=mvindex(split($full_url$,"?"),0), base_url:=if(isnull(base_url),full_url,base_url), host=mvindex(split($full_url$,"?"),1) 

    # we have copied the URL paramaters to host, lets extact this and extract the paramaters one by one creating indexed fields
    [enrich_splunkd_access_log-extract_url_parameters_from_host_to_meta]
    SOURCE_KEY = MetaData:Host
    WRITE_META = true
    REGEX = ([^=&:]+)=([^&]+)
    FORMAT = rest_param_$1::"$2"
    REPEAT_MATCH = true

    # copy back my_host to host and drop my_host
    # we don't want to index the full url as it is will bloat tsidx,  we don't need my_host 
    [enrich_splunkd_access_log-meta_copy_back]
    INGEST_EVAL=host:=my_host, my_host:=null(), full_url:=null()
