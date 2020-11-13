# Problem statement
The throughput of a single pipeline is about 20MB/s dependant on CPU etc. Many forwarders need to send an excess of 20MB/s but doing so can saturate an indexer. These are jokingly referred to as "laser beams of death" as they can overwhelm an indexers pipeline and causes event delay issues for all data passing through that indexer. 

## Existing solution
This issues is normally resolved by adding more pipelines to the forwarder sending data. Also the features autoLBVolume and / or lowering the autoLBFrequency. However these solutions fail when the input source cannot be mapped across multiple pipelines. In this instance increasing pipelines or switching does not help

# Proposed solution
For parsed events, i.e. those that are going through a HWF we can use event routing and INGEST_EVAL to randomly direct events to multiple output stanzas. In this instance we will use two output groups.

### props.conf

    # This sourcetype sends data out via TCP out
    [split_forwarding]
    TIME_PREFIX = ^
    TIME_FORMAT = %Y-%m-%d %H:%M:%S
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    rename = split_forwarding_recieved
    TRANSFORMS-split_forwarding=split_forwarding-randomize_output


### transforms.conf

    # this transform randomly assigns each event to one of the two output groups by appending a 0 or 1 to the named output group
    [split_forwarding-randomize_output]
    INGEST_EVAL = _TCP_ROUTING="split_forwarding_".random()%2

### outputs.conf

    [tcpout:split_forwarding_0]
    server=server_a:9997,server_b:9997
    autoLBVolume=100000
    autoLBFrequency=1
    sendCookedData=true
    dropEventsOnQueueFull=2
    maxQueueSize=auto

    [tcpout:split_forwarding_1]
    server=server_a:9997,server_b:9997
    autoLBVolume=100000
    autoLBFrequency=1
    sendCookedData=true
    dropEventsOnQueueFull=2
    maxQueueSize=auto

    [tcpout]
    defaultGroup=split_forwarding_0
    compressed=true
    sendCookedData=true