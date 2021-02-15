# Problem description

Some data contains private or secret information like user names and passwords that it is inappropiate for all eyes to see. Under these circumstances data needs to be hidden from those users, for instance 1st line support. However this we may still need to keep the orginal data for other reasons, for higher security level users. Splunk doesn't allow for selective masking at point of search, which is a significant challenge for any unstructured data system.

## Existing Solutions
Splunk documentation a section on how to [Anonymize data|https://docs.splunk.com/Documentation/Splunk/8.0.6/Data/Anonymizedata]. However this is destructive to the orignal event and the ability to see the orginal event is lost. 


## Proposed Solution
This problem has been addressed in the example [mask and map|mask_and_map], this solution works but it results in double ingestion costs and the semi masking of email addresses isn't great. This solution also uses `CLONE_SOURCETYPE` to create another version of the event, but in this instance we will use a hashing algorithm to encode both the user and the password. The cloned event will have indexed fields to hold a map to undo the map. We can then combine the events to undo the map effeciently at search time. This approach allows for some cool functionality that could not be implemented with a lookup.

###  Example log line

    23:16:25 20-09-23 my email_address=julian@wikileaks.com and my terrible password="onetimepassword"

### The steps performed to process data

1. We intercept the data under the `mask_data_and_map` sourcetype, before we clone the event we need to do some work
   1. Extract the email address using a regex transform and store the email address as an indexed field
   2. Extract the password using a regex transform and store the password as an indexed field 
2. We create encoded versions of the indexed fields for password and email address
   1. We compute the hash on the email field but only keep the first 10 charactors so that the event doesn't become excessively long `substr(sha1(email_address),0,10)` 
   2. We compute the hash of the password AND email field, this means that it is not possible to search for users using the same password, i.e. the hash is scoped the email address. Yet we are able to see if the user has changed their password
3. We clone the event ...
   1. ... with the original 
      1. We update the `_raw` string using the `replace` function to swap the unencoded values with the new encoded ones
      2. We remove the encoded and unencoded indexed fields 
   2. ... with the cloned event 
      1. We replace the `_raw` string with a single charactor to reduce licensing
      2. We keep the indexed fields which become the translation

When we search the event we are able to efficently match the encoded log line and the mapping because they appear at the same moment in time.

    index=ingest_eval_examples* sourcetype=mask_data_and_map-map OR sourcetype=mask_data_and_map
    | stats values(eval(if(_raw!=".",_raw,NULL))) as _raw 
        values(password_decoded) as password_decoded
        values(email_address_decoded) as email_address_decoded
        by _time password email_address
    | table _time _raw email_address_decoded password_decoded

#### props.conf

    # This is a much more complex masking that creates an cloned event that is transformed into a "map"
    [mask_data_and_map]
    TIME_PREFIX = ^
    TIME_FORMAT = %H:%M:%S %y-%m-%d
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-apply-masking=mask_data_and_map-extract_email, mask_data_and_map-extract_password, mask_data_and_map-encode_email_and_password, mask_data_and_map-clone, mask_data_and_map-apply_hashes

    # Take the cloned event, transform to a map and send to a different index
    [mask_data_and_map-clone]
    TRANSFORMS-create_map = shared-route_to_ingest_eval_examples_2, mask_data_and_map-create_map
    rename=mask_data_and_map-map

#### transforms.conf

    # This REGEX extracts the password string from the event. This is used instead of the INGEST_EVAL replace function because it will use compilied REGEX
    # Using REGEX on a password is interesting as we have no idea what is in the password, it could contain whitespace or any other charactor
    # For the example event we know it is the last field and we are able to match on $ for the end of the string
    [mask_data_and_map-extract_password]
    SOURCE_KEY = _raw
    WRITE_META = true
    REGEX = password="(.*)"$
    FORMAT = password::"$1"

    # This REGEX extracts the email address, we could merge this REGEX with the extract password if we wanted
    # Again we prefer REGEX over replace() for the assumed performance boost
    [mask_data_and_map-extract_email]
    SOURCE_KEY = _raw
    WRITE_META = true
    REGEX = email_address=(\S+@\S+)
    FORMAT = email_address::"$1"

    # This REGEX transform CLONES the data, for some reason it has to do a REGEX match and replace, this is cheap one as host is short and we only match a single charactor
    [mask_data_and_map-clone]
    SOURCE_KEY = Meta:Host
    DEST_KEY = Meta:Host
    REGEX = (.)
    FORMAT = %0
    CLONE_SOURCETYPE = mask_data_and_map-clone

    # We want to get an encoded username and password so that we can track user names annoymously, however we don't want users to have the ability to see which users share the same password
    # To stop this, we include the user name in the hash with the password, this allows us to see if the password has been changed, but much harder to work out if passwords are shared
    # We perform this operation before we clone, so that the heavy SHA1 computation is used once. Also to make the output easier to read we clip off the first 10 charactors rather
    # than insert a long string into the event
    [mask_data_and_map-encode_email_and_password]
    INGEST_EVAL =  email_address_encoded=substr(sha1(email_address),0,10), password_encoded=substr(sha1(email_address.password),0,10)

    # We take the original clone event and use replace to swap out the email address and password for the encrypted versions, then we drop the encoded password etc.
    # We also drop the password and user name, although this isn't necessary and it might be more useful to keep as indexed fields
    [mask_data_and_map-apply_hashes]
    INGEST_EVAL = _raw=replace(_raw, "email_address=\S+", "email_address=".email_address_encoded), _raw=replace(_raw, "password=\".*\"$","password=\"".password_encoded."\""), email_address:=null(), password :=null(), password_encoded:=null(), email_address_encoded:=null()

    # The cloned event is going to be turned into a map. We set the _raw string to be . to save on license costs and shuffle around the field names to make it easier to use at search time
    [mask_data_and_map-create_map]
    INGEST_EVAL = _raw=".", email_address_decoded:=email_address, email_address:=email_address_encoded, password_decoded:=password, password:=password_encoded, password_encoded:=null(), email_address_encoded:=null

    # routes the cloned data to a different index
    [shared-route_to_ingest_eval_examples_2]
    INGEST_EVAL = index="ingest_eval_examples_2"
