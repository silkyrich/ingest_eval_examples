# Problem statement
Some applications place the timestamp and the date stamp in different locations. For instance we might find that the file name or directory contains the date, but only the timestamp is found in the file.

## Existing solution
Currently the only solution is to use `datetime.xml`, however the author is blissfully unaware on how this might be achieved.

# Alternative approach 
With the introduction of `INGEST_EVAL` we now have an approach using the tools we already know.

### Example data
To demonstrate how `INGEST_EVAL` can resolve the issue this application generates some sample data. Notice how the file name contains the date, but the log file contains the time.

    (base) my-host:compound_date_time user$ ls -l
    total 152
    -rw-r--r--  1 user  wheel  1052 17 Aug 22:15 2020-08-17.log
    -rw-r--r--  1 user  wheel   808 17 Aug 22:15 2020-08-18.log
    -rw-r--r--  1 user  wheel   891 17 Aug 22:15 2020-08-19.log
    -rw-r--r--  1 user  wheel   932 17 Aug 22:15 2020-08-20.log
    -rw-r--r--  1 user  wheel  9063 21 Aug 20:19 2020-08-21.log
    -rw-r--r--  1 user  wheel  8692 21 Aug 20:19 2020-08-22.log

    (base) my-host:compound_date_time user$ head -10 2020-08-17.log 
    01:23:11 splunk> Digs deeper than a jealous spouse.
    03:42:27 Splunk> Be an IT superhero. Go home early.
    04:07:08 splunk> More flexible than an Olympic gymnast.
    04:24:47 splunk> Walking War Room!!
    04:30:41 Splunk> see the light before you tunnel
    06:10:07 Splunk> data with destiny
    06:29:28 splunk> More flexible than an Olympic gymnast.
    06:52:00 splunk> ""\. nuff said.
    07:52:59 Splunk> Take the sh out of IT.
    08:44:00 Splunk> See your world. Maybe wish you hadn’t.


### Steps

1. Set the incoming data to use `CURRENT_TIME`
1. Use `replace` function to extract (using REGEX) the datestamp from the file name
1. Use `substr` to extract the time component from the `_raw` string
1. Join the date and time strings together
1. Apply a custom `strptime` extraction to extract the time and date from the compound string 

### props.conf

    # This sourcetype is for the compound datetimes examples where the file name encodes the date stamp
    # but the timestamp is per log line
    [compound_date_time]
    DATETIME_CONFIG = CURRENT
    TRANSFORMS-get-date = construct_compound_date
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)


### transforms.conf

    # use regex replace to pop out the date form the source, append on the first 10 chars from _raw and then run through strftime.
    # if the eval fails to execute, CURRENT time will be kept
    [construct_compound_date]
    INGEST_EVAL= _time=strptime(replace(source,".*/(20\d\d\-\d\d\-\d\d)\.log","\1").substr(_raw,0,10),"%Y-%m-%d%H:%M:%S"), my_date:=null() 
