# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Class  : SparkStreamingWordCount                                               *
# * Created: 2017/07/12                                                            *
# * Description:                                                                   *
# *      The Spark Streaming word count example derived from:                      *
# *      https://spark.apache.org/docs/latest/streaming-programming-guide.html     *
# *                                                                                *
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

from eskapade import ProcessManager, ConfigObject, Link, DataStore, StatusCode
from eskapade.spark_analysis import SparkManager
from pyspark.sql import Row


class SparkStreamingWordCount(Link):
    """ Counts words in UTF8 encoded delimited text 

    Text is received from the network every second.
    To run this on your local machine, you need to first run a Netcat server

    `$ nc -lk 9999`

    and then run the example (in a second terminal)

    `$ run_eskapade tutorials/esk610_spark_streaming_wordcount.py`

    NB: hostname and port can be adapted in the macro
    """

    def __init__(self, **kwargs):
        """Initialize SparkStreamingWordCount instance

        :param str name: name of link
        :param str read_key: key of input data to read from data store
        :param str store_key: key of output data to store in data store
        """

        # initialize Link, pass name from kwargs
        Link.__init__(self, kwargs.pop('name', 'SparkStreamingWordCount'))

        # process keywords
        self._process_kwargs(kwargs, read_key=None, store_key=None)
        self.check_extra_kwargs(kwargs)

    def initialize(self):
        """Initialize SparkStreamingWordCount"""

        return StatusCode.Success

    def execute(self):
        """Execute SparkStreamingWordCount"""

        proc_mgr = ProcessManager()
        settings = proc_mgr.service(ConfigObject)
        ds = proc_mgr.service(DataStore)

        lines = ds[self.read_key]
        counts = lines.flatMap(lambda line: line.split(" "))\
            .map(lambda word: (word, 1))\
            .reduceByKey(lambda a, b: a + b)
        counts.pprint()

        if self.store_key is not None:
            ds[self.store_key] = counts

        return StatusCode.Success

    def finalize(self):
        """Finalize SparkStreamingWordCount"""

        return StatusCode.Success
