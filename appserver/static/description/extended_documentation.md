# INGEST_EVAL Extended Documentation

The public facing [documentation](https://docs.splunk.com/Documentation/Splunk/8.1.0/Data/IngestEval#Examples)  on `INGEST_EVAL` does not 
include all the details mentioned in our internal developer documentation. In particular it doesn't mention details on how `_time`, 
how to handle `multi-value` fields or how to debigulate between `pipelineData` fields. This documentation is adapted from internal notes exchanged between developers and is presented as is.

---
# ingest-time transforms via transforms.conf

Here is a snippet of what a configuration looks like for props and transforms when using regex transforms and is well documented 
in [Getting Data In](https://docs.splunk.com/Documentation/Splunk/8.1.0/Data/Configureindex-timefieldextraction#Define_additional_indexed_fields)

Data streams are targeted via `sourcetype`, `host` or `source` in `props.conf` which can optionally apply transforms to that stream. 
For instance, in the example below we have configured the sourcetype `mysourcetype` to have two regex transforms applied to it, `regex1` and `regex2` which are 
defined in `transforms.conf`

## props.conf

```
[mysourcetype] 
TRANSFORMS-foo=regex1,regex2
```
## transforms.conf

```
[regex1] 
REGEX=^foo-([A-Z]*) 
FORMAT= foo::$1

[regex2] 
REGEX=bar-([0-9]*)$ 
FORMAT=bar::$2
```
---
# What's New?

Some ingest-time transformations are hard or impossible using regexes alone. For example, regex transforms don’t help much for metrics 
normalisation. Reusing the existing power of the search-time `| eval` operator makes some of these very simple to write. 

* An ingest-time `INGEST_EVAL` is simply another type of transforms.conf stanza
* The evaluations to run are selected in the exact same way in props.conf
* Regex-based and `INGEST_EVAL`-based transforms can be combined in any order!

Additionally, it gives savvy developers more direct control of index-time fields than they had before. A developer can control exactly 
how an index time field will be stored in the journal. We’ll see examples of this later

## Example of an INGEST_EVAL transform stanza:
```
[eval1]
INGEST_EVAL= field3=length(_raw)*2
```
The evaluation language is identical to the search-time `INGEST_EVAL` command, so refer to our documentation on [`| eval`](https://docs.splunk.com/Documentation/Splunk/latest/SearchReference/Eval) 
for further details.

## Multi-Eval support
Just like on the search-time [`| eval`](https://docs.splunk.com/Documentation/Splunk/latest/SearchReference/Eval) command, multiple comma-separated expressions can be chained:

```
[eval2]
INGEST_EVAL= field4=_time, field5=field4+1
```
---

# Defining Variable Names
Most of the common `PipelineData` keys that transforms.conf normally operates on (`_raw`, `index`, `queue`, ...) can be read or written directly:
```
INGEST_EVAL= index=“split_“+substr(sha1(_raw),1,1)
INGEST_EVAL= queue=if(random()%3==0,”nullQueue”,”indexQueue”)
```
Also, several search-time variables work as expected (`source`, `sourcetype`, `host`, ...)

```
INGEST_EVAL= queue=if(linecount>100,”nullQueue”,”indexerQueue”)
INGEST_EVAL= sourcetype=if(substr(_raw,1,1)==“#”,”comment”,sourcetype)
```

But by default, variables refer to index-time fields. This is the same place that a regex-based transform writes its output 
(in the familiar
`key::value` form). These are also known as `_meta` fields because of where they are stored internally to `PipelineData`

For example these two transforms create equivalent results:
```
[x1]
REGEX=.* 
FORMAT=fieldname::3

[x2]
INGEST_EVAL= fieldname=1+2
```

This normally just “does what you want”, but the decision about whether a variable is a `PipelineData` key or a `indextime` field can also be overridden by using eval’s dollar-sign format
```
INGEST_EVAL= $field:myfield$=length($pd:_raw$)
```

Again, normally this verbosity isn’t needed — whether a variable is an indextime field or not is clear from context.

---
# Handling the `_time` field
As an aside: `_time` works like at search-time (i.e. includes subseconds) 

```
INGEST_EVAL= until_sec=ciel(_time)-_time
```

However, the `PipelineData` time doesn’t have the subseconds-part included yet, and that can be manipulated via `$pd:_time$`

```
INGEST_EVAL= $pd:_time$=1500000000+(random()%100000)
```
---
# Multivalue indexed fields
Index-time fields can have multiple values.
These can be created similarly to search-time multival fields. 

Here is another example of functional equivalency between `regex` and `INGEST_EVAL` transforms

```
[multi1]
REGEX=.*
FORMAT=x::a x::b x::c

[multi2]
INGEST_EVAL= x=mvappend(“a”,”b”,”c”)
```

However, by default when reading an eval field, only the first value is used: This can be overridden by using `$mv:field$`

```
mvjoin(x,”.”) => “a” 

mvjoin($mv:x$,”.”) => “a.b.c"
```

This may seem odd at first, but multi value fields are a rarely-used feature, and fetching only the first value is much more efficient

Just as with regex-based transforms, by default an eval-based transform creates a new `indextime` field
```
INGEST_EVAL= z=10, z=z+1
```
Produces `z::10 z::11`

This can be changed by using `:=` as the assignment operator:
```
INGEST_EVAL= z=10, z:=z+1
```
Produces `z::11`

Note that there is a slight performance penalty, so it’s best to only do this when it’s possible the field already exists.

This `:=` format can also be used to remove an existing index-time field:

```[remove-xyz] 
INGEST_EVAL= xyz:=null()
```

---
# A note on types

Internally (both in RAM and on disk) an `indextime` field can hold its value in multiple ways: a string, an integer, several floating-point representations
With regex-based transforms the developer had no control over this; they were essentially always strings
Only internal code (like metrics) could really take advantage of other value types

With `INGEST_EVAL` based transforms, each evaluation can optionally control the type an `indextime` field will be stored in. Some simple examples:

```
INGEST_EVAL= field_a[int]=length(_raw) 
INGEST_EVAL= field_a[float]:=log(field_a)
```

For floating-point numbers, you can also specify that the number of significant digits of the calculation must be kept by adding `-sf` to the type:
```
INGEST_EVAL= a[float-sf]=b*1.35
```

Also a less precise (but smaller) encoding is available as `float32`/`float32-sf` 
```
INGEST_EVAL= bits_per_second[float32]=bytes_per_second*8
```
This can be used to trim the size of metrics data, for instance. Even an existing field can have its type changed:
```
INGEST_EVAL= myfield[float32]:=myfield
```

By default, a sane result type is chosen from the expression
i.e. a numeric result will be stored as a number, a string as a string, a multi value as a series of strings, etc
So for most cases, specifying an explicit type is not needed.

---
# High-cardinality strings - a warning

The `indextime` field system was originally built to handle two use cases:
1. Low-cardinality “tags” on events (“date_month::july”) 
1. Substrings extracted from `_raw` via CSV or JSON parsing

This means in our on-disk index format, strings can take one of two formats:

1. A single integer referring to a value stored in Strings.data
2. A pair of integers describing the offset of the string inside `_raw` and its `length` (with some small tweaks to allow CSV/JSON quoting)

•	This means that high-cardinality string values that don’t originate as part of `_raw` can be very inefficient, both for indexing and searchtime!
(None of this is new, just something to keep in mind)

## Examples:

Here are some examples around cardinality of strings when applied to indexed fields.

### Good - Low cardinality string 
```
INGEST_EVAL= sev=if(val>100,”RED”,if(val>50,”YELLOW”,”GREEN”))
```

### Good - We can detect that the result is a _raw substring! 
```
INGEST_EVAL= col3=substr(_raw,20,10)
```

### BAD! - The storage engine doesn’t currently have a way of storing this high-cardinality field efficiently
```
INGEST_EVAL= hash=sha1(_raw)
```

### BAD! - High precision numbers create more cardinality
```
INGEST_EVAL= number=random()
```

### Good - Low precision numbers have reduced cardinality
```
INGEST_EVAL= number=round(random(),5)
```

