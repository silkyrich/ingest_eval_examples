# Problem statement
Some sources can contain conflicting date time formats and Splunk applies parsing logic per sourcetype. This is frequently the case when recieving syslog data or reading from tcp.


## Existing solution
Splunk documentation mentions that this can be a problem on the page [Configure timestamp assignment for events with multiple timestamps](https://docs.splunk.com/Documentation/Splunk/latest/Data/Configurepositionaltimestampextraction) and outlines how to [Configure advanced timestamp recognition with datetime.xml](https://docs.splunk.com/Documentation/Splunk/latest/Data/Configuredatetimexml). 

This approach works but requires that the adminstrator understands and builds a custom `datetime.xml` files, using the defualt one can be especially problematic as it assumes the US date format over others. 

## Alternative approach 
With the introduction of `INGEST_EVAL` we now have an approach using the tools we already know.

### Steps

1. Set the incoming data to use `CURRENT_TIME`
1. Use `INGEST_EVAL` to repeatedly test strfime formats until one matches

### props.conf
    # This sourcetype is for the conflicting timestamps usecase, it calls a transform to extract the 
    # datetime format via INGEST_EVAL and the strptime function
    [demutliplexed_datetime_formats]
    DATETIME_CONFIG = CURRENT
    TRANSFORMS-extract_date = demultiplex_datetime
### transforms.conf

    #  This transform tests three different date time formats and selects the first that matches
    [demultiplex_datetime]
    INGEST_EVAL= _time=case(isnotnull(strptime(_raw, "%c")), strptime(_raw, "%c"), isnotnull(strptime(_raw, "%H:%M:%S %y-%m-%d")),strptime(_raw, "%H:%M:%S %y-%m-%d"), isnotnull(strptime(_raw, "%Y-%m-%d %H:%M:%S")), strptime(_raw, "%Y-%m-%d %H:%M:%S"))


