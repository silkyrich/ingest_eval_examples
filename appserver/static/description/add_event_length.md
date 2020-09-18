# Problem statement 

Splunk either charges by vCPU or by license usage. Whichever method is used license reporting goes into the `license.log` file and usage it attributed to `sourcetype`, `host` and `index`. This is sufficent for Splunk to assess licence usage and attribute to high level sources. Occasionally you may wish to further breakdown how license usage is being consumed, perphaps attributing to multiple dimensions for instance this host and this sourcetype. 

Also sourcetypes like `stash`, or indexes like `_internal` do not write any data to license.log and it therefore difficult to judge how many MB has been ingested in these cases.

## Existing solution
You can write searches on `license.log` for crude roll ups per sourcetype and index. Alternatively you can estimate usage by computing the average len of your events and multipling by the number of events. 

# Alternative approach 
With the introduction of `INGEST_EVAL` we can add an indexed field that contains the length of the `_raw` string and then use `tstats` to compute license usage accurately and effciently at large over long durations with far more complex logic.

### Steps

1. Set the `default` sourcetype to catch very event passing through the ingestion pipeline
1. Set the `transform` to have a name that comes last in the evaluation logic
1. Use `INGEST_EVAL` to compute the length of `_raw` and apply to the field `event_length`

### props.conf

    # This configuration is applied to all sourcetypes and it adds an indexed field with len of the event
    # This is very useful for using with tstats to sum up all ingested data from any source very quickly
    [default]
    TRANSFORM-all-data= add_raw_length_to_meta_field

### transforms.conf

    # add the length of the _raw string to the event, this needs to be the last transform so we don't change the
    # length of _raw again once the value has been computed
    [add_raw_length_to_meta_field]
    INGEST_EVAL= _event_length=len(_raw)

