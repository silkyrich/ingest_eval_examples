
# Set up the global variables for the script

import json
import os
import pandas
import math
import random
import datetime
import uuid

""" 
For events we have selected a selection of Splunk T shirt sloans. This list was obtained by searching the web, it is not a definitive list and I suspect many were never printed :-)
"""
log_lines = open("sample/splunk_slogans.txt","r").read().splitlines()

"""
The script generates events randomly over a time range, by default this goes back 5 days and generates a 1000 events each time.
"""
date_range_days=2
sample_readings=1000

# Get an random array of datetime objects going backwards in time, sorted oldest first
def get_dates(sample_readings : int, max_days_ago : int) : 
    datetimes = []
    for i in range(0,sample_readings): 
        random_seconds = random.randrange(1, max_days_ago*24*60*60)
        my_timedelta=datetime.timedelta(seconds=-random_seconds, milliseconds=random.randint(0,9999))
        my_datetime=datetime.datetime.now()+my_timedelta
        datetimes.append(my_datetime)
    # Sort the dates into reverse chroniclogical order as they would appear in a log file
    datetimes.sort(reverse=False)
    return datetimes

"""
This generates a list of events where the time stamps switches between 3 different timestamps.

This is a common problem in badly designed Splunk instances. People open a TCP port and then fire all sorts of different data in there. 

Ideally we would create multiple sourcetypes and then assign a TCP port for each sourcetype. However the example shows you how to patch the problem during ingestion.
"""
def generate_conflicting_dates(sample_readings : int, max_days_ago : int) :

    # our three different date time formats
    datetime_format = ["%Y-%m-%d %H:%M:%S", "%H:%M:%S %y-%m-%d", "%c"]

    # create out output file
    mutliplexed_datetime_formats = open("sample/conflicting_dates/mutliplexed_datetime_formats.log","w")

    # iterate through the list of date timesn and write out to disk
    for my_datetime in get_dates(sample_readings, max_days_ago) :
        # select a timeformat at random and use it
        time=my_datetime.strftime(random.choice(datetime_format))
        # pick a random log line to use
        message=random.choice(log_lines)
        # write out the log file
        mutliplexed_datetime_formats.write(time+" "+message+"\n")

    # close and flush the file
    mutliplexed_datetime_formats.close()


"""
This script generates events where the date is embedded in the file name, but the timestamp is per event im the contents of the file.

We are going to create a map of dates to times, so that we can itterate through each day, create a file and fill with events for that day

To work around any weird rounding errors due to timezones we will generate the day, and the seconds separately
"""
def generate_files_for_dates(sample_readings : int, max_days_ago : int) : 
    # create our map for the date to timings mapping
    date_map = {}

    # populate our map
    for my_datetime in get_dates(sample_readings, max_days_ago) :
        # get the date component from the datetime object
        day=my_datetime.strftime("%Y-%m-%d")
        if day not in date_map :
            date_map[day] = []
        date_map[day].append(my_datetime.strftime("%H:%M:%S.%f"))            

    # itterate through all the days and print out the times with a random log message
    for my_day in date_map.keys() :
        filename="sample/compound_date_time/"+my_day+".log"    
        # filename for the days events, named after the day "2020-02-12.log"
        file_for_day = open(filename,"w")
        for my_time in date_map[my_day] :
            # write out the timestamp with a random log message
            file_for_day.write(my_time + " " + random.choice(log_lines)+ "\n")

"""
This script generates a csv with 'useless' columns that we don't want to add into tsidx because they will bloat the size of the bucket.

We use pandas to build the CSV file, set headers etc
"""

def generate_drop_columns_csv(sample_readings : int, max_days_ago : int)  :
    # create a pandas with some column headings describing the contents
    useless_columns=pandas.DataFrame(columns=['primary_key', 'primary_value', 'repeated_field', 'random_nonsense', 'long_payload'])

    # Create rows and assign values to the columns
    for my_date in get_dates(sample_readings, max_days_ago) :
        useless_columns=useless_columns.append({'primary_key': my_date, 'primary_value': random.randint(0,999999), 'repeated_field': "same silly value", 'random_nonsense' : uuid.uuid4(), 'long_payload' : random.choice(log_lines)}, ignore_index=True)

    # write out the CSV file
    useless_columns.to_csv('sample/drop_useless_columns/useless_columns.csv', sep=',', encoding='utf-8', index=False)

"""
This creates log lines with follow an attribute=value pattern using different and no quotes

Specify the minimum and maximum number of av pairs per log line
"""
def generate_indexed_fields_log(sample_readings : int, max_days_ago : int,  min_values : int, max_values : int) : 

    # a list of variable names for us to pull from, complete with a type field
    variable_names= [('stdev_kbps',float),('average_kbps',float), ('sum_kbps',int), ('label',str), ('name',str), ('group',str), ('value',int)]
    # a list of string values for us to pull from when building events
    labels = ['no_quotes',"'single quotes'",'"double quotes"']

    # We don't want some n00b specifying more AV pairs than we have in our sample group or we run out!
    if (max_values>len(variable_names)) :
        max_values=len(variable_names)

    # open our output file
    indexed_log = open("sample/indexed_log/indexed.log","w")

    # get a selection of date times
    for my_datetime in get_dates(sample_readings, max_days_ago) :

        # We don't want the same variable printed multiple times, this would result in multivalue fields   
        # Copy the our list of possible AV pairs     
        my_variables_names=variable_names.copy()
        # shuffle that list so they occur in a random order
        random.shuffle(my_variables_names)

        # we need an message to return, we will put the time stamp at the front
        message = my_datetime.strftime("%Y-%m-%d %H:%M:%S") 

        # We will append a random number of AV pairs to the message
        for i in range(0,random.randint(min_values,max_values)) :
            # pop off the variable name and the type that we are going to use
            (variable_name, variable_type) = my_variables_names.pop(1)
            # write out the variable name
            message = message + " " + variable_name + "=" 
            # depending the type select a value
            if (variable_type == str) : 
                message = message + random.choice(labels)
            elif (variable_type == float) :
                message = message + str(random.random())
            elif (variable_type == int) :
                message = message + str(random.randint(0,9999))

        # write out the log name
        indexed_log.write(message+"\n")

    # close the file
    indexed_log.close()

"""
This script generates a data set for importing into directly into splunk. We have create sourcetype, source, host, index and then use INGEST_EVAL + REGEX to extract the fields and copy them into the relevant fields. 

The format aims to replicated the output of the following splunk search:
"""
def generate_input_file (sample_readings : int, max_days_ago : int) :

    # for this demo we needs some target indexes, sourcestypes, sources and hosts

    # these indexes have been created in indexes.conf
    indexes=['ingest_pipeline_demo_a', 'ingest_pipeline_demo_b']
    # sourcetypes should have only one date format, lets match these together, these don't need to be defined in props.conf as the timestamp is written out in EPOCH
    sourcetypes=[('fruit', "%c"), ('beef', "%Y-%m-%d %H:%M:%S"), ('fish', "%H:%M:%S %y-%m-%d"), ('chicken', "%d %a %Y %H:%M:%S")]
    # a selection of values for source
    sources=['sea', 'ground', 'sky', 'tree']
    # a selection of values for host
    hosts=['farm_shop', 'online', 'super_market', 'market']
    # we also need something to separate the data
    sep="%%%"

    # open the output log file to write data too
    import_events = open('sample/import_data/encoded_splunk_events.csv',"w")

    # get a selection of date times
    for my_datetime in get_dates(sample_readings, max_days_ago) :
        # pick a sourcetype adn 
        (sourcetype, datetime_format) = random.choice(sourcetypes)
        # get the epoch numeric value for the datetime
        time=str(my_datetime.timestamp())
        # pick a random host, source and index for the log line
        host=random.choice(hosts)
        source=random.choice(sources)
        index=random.choice(indexes)
        # generate the log line prefixed by the timestamp
        raw=my_datetime.strftime(datetime_format)+" "+random.choice(log_lines)
        # write out the line to be written into the import file
        import_events.write(time + sep + index + sep + host + sep + source + sep + sourcetype + sep + raw + "\n")

    # write to the output file
    import_events.close()

""" This function generates a text file with user names and passwords so we can demonstrate how to mask data
"""

def generate_password_problems(sample_readings : int, max_days_ago : int) :

    # a selection of comedy passwords, for more bad passwords I recommend the excellent https://bad.pw/
    terrible_passwords = ["password", "p@$$w0rd", "qwerty123", "aaaaa", "admin", "0000", "letmein", "onetimepassword", "assword", "abc123", "123456", "password1", "iloveyou", "trustno1", "iambatman"]
    email_addresses = ["admin@ghcq.com", "007@mi5.gov.uk", "putin@gru.ru", "director@cia.us.gov", "julian@wikileaks.com", "jbourne@ucia.gov"]

    joke_security=open("sample/security_data/insecurity.log", "w")

    for my_datetime in get_dates(sample_readings, max_days_ago) :
        joke_security.write(my_datetime.strftime("%H:%M:%S %y-%m-%d") + " my email_address=" + random.choice(email_addresses) + ' and my terrible password="' + random.choice(terrible_passwords) + '"\n')
   
    joke_security.close()

generate_conflicting_dates(1000,10)
generate_drop_columns_csv(100,10)
generate_files_for_dates(1000,5)
generate_indexed_fields_log(1000,10,2,5)
generate_input_file(1000,5)





