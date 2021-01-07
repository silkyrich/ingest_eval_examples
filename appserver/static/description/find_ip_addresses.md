# Problem statement

Searching for IP addresses in Splunk is super expensive due to how the indexing process works. Specifically when a user searches for `index=something dest=10.20.30.1` the platform generates a LISPY `[ AND 1 10 20 30 index::something ]` which matches any event containing `1`, `10`, `20`, `30` and then relies on schema on the fly to sure they are in sequence and in the right order. This elimination after schema on the fly is very wasteful and early elimination at the lexicon stage would return huge dividends.

## Proposed Solution

We use REGEX to extract things that appear to be ip address and write them into an indexed field. We can then modify our searches to use that indexed field for accelaration.

For example we take our search `index=something 10.20.30.1` and add the reference to the indexed field `index=something ip::10.20.30.1 dest=10.20.30.1`. This changes the LISPY so that it includes the indexed field `[ AND 1 10 20 30 index::something ip::10.20.30.1 ]` which then eliminates events that contain `1`, `10`, `20`, `30` but are not IP addresses, for example `1/30/20 value=10` 


