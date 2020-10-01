# Problem description
Some data contains private or secret information like user names and passwords that it is inappropiate for all eyes to see. Under these circumstances data needs to be hidden from users. However this we may still need to keep the orginal data for other reasons. Splunk doesn't allow for selective masking at point of search. 

## Existing Solutions
Currently we are only able to use SED or REGEX commands to change the `_raw` string, however this is dificult to implement. 

## Proposed Solution
It is possible to implement this solution using entirely using the `INGEST_EVAL` and `replace()`, but in the interests of  

###  Example log line

    09-18-2020 10:02:11.793 +0100 INFO  LicenseUsage - type=Usage s="my_host" st="m_sourcetype" h="my_host" o="" idx="default" i="18F9C3EA-EBB2-497C-801A-098D0C52F9E2" pool="auto_generated_pool_enterprise" b=2034451 poolsz=53687091200

### The steps performed to process data

1. 

#### props.conf

    # This sourcetype is cloned and the clone has masking applied, the orignal remains untouched and is routed to the 'secure' index
    [mask_and_clone]
    TIME_PREFIX = ^›
    TIME_FORMAT = %H:%M:%S %y-%m-%d
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+) 
    # this transform will create a new event with a tempoary sourcetype
    TRANSFORMS-apply-masking=mask_and_clone-clone

    # we intercept the tempory sourcetype, apply some sed transforms, rename the sourcetype to the original and route to another 'insecure' index
    [mask_and_clone-clone]
    # because we have created a new event we can apply a SED transform to the newly created event
    # we could use the INGEST_EVAL replace function to do this, but using SED is slighly more elegent and is likely use a faster engine and the replace function.
    # Note that we have specfied two SED commands separated by a space
    SEDCMD-mask = s/email_address=(\S\S)\S*(.)@(.)\S*(\S\S\S)\s/email_address=\1..\2@\3..\4 /g s/password=\S+/password=#######/g
    # we need to route this new event to another index to prove our solution
    TRANSFORMS-route-to-index = shared-drop_useless_time_fields, mask_and_clone-route_to_index
    # we can set the sourcetype back to the orginal
    rename = mask_and_clone

#### transforms.conf

    # we create a clone
    [mask_and_clone-clone]
    SOURCE_KEY = Meta:Host
    DEST_KEY = Meta:Host
    REGEX = (.)
    FORMAT = %0
    CLONE_SOURCETYPE = mask_and_clone-clone

    # routes the cloned data to a different index
    [shared-route_to_ingest_eval_examples_2]
    INGEST_EVAL = index="ingest_eval_examples_2"
