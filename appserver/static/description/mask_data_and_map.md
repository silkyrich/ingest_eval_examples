# Problem description

.

## Existing Solutions
.

## Proposed Solution
.

###  Example log line

    09-18-2020 10:02:11.793 +0100 INFO  LicenseUsage - type=Usage s="my_host" st="m_sourcetype" h="my_host" o="" idx="default" i="18F9C3EA-EBB2-497C-801A-098D0C52F9E2" pool="auto_generated_pool_enterprise" b=2034451 poolsz=53687091200

### The steps performed to process data

1. 

#### props.conf

    # This is a much more complex masking that creates an cloned event that is transformed into a "map"
    [mask_data_and_map]
    TIME_PREFIX = ^
    TIME_FORMAT = %H:%M:%S %y-%m-%d
    SHOULD_LINEMERGE=false
    LINE_BREAKER=([\n\r]+)
    TRANSFORMS-apply-masking=shared-drop_useless_time_fields, mask_data_and_map-extract_email, mask_data_and_map-extract_password, mask_data_and_map-encode_email_and_password, mask_data_and_map-clone, mask_data_and_map-apply_hashes

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