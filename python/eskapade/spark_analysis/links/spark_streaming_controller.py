# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Class  : SparkStreamingController                                              *
# * Created: 2017/07/12                                                            *
# * Description:                                                                   *
# *      Link to start/stop Spark Stream.                                          *
# *                                                                                *
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

import time

from eskapade import ProcessManager, ConfigObject, Link, DataStore, StatusCode
from eskapade.spark_analysis import SparkManager


class SparkStreamingController(Link):
    """Defines the content of link SparkStreamingController"""

    def __init__(self, **kwargs):
        """Initialize SparkStreamingController instance

        :param str name: name of link
        :param str read_key: key of input data to read from data store
        :param str store_key: key of output data to store in data store
        :param int timeout: the amount of time (in seconds) for running the Spark Streaming Context
        """

        # initialize Link, pass name from kwargs
        Link.__init__(self, kwargs.pop('name', 'SparkStreamingController'))

        # process keywords
        self._process_kwargs(kwargs, read_key=None, store_key=None, timeout=None)

        # check residual kwargs; exit if any present
        self.check_extra_kwargs(kwargs)

    def initialize(self):
        """Initialize SparkStreamingController"""

        # check input arguments
        self.check_arg_types(timeout=int)

        return StatusCode.Success

    def execute(self):
        """Execute SparkStreamingController"""

        proc_mgr = ProcessManager()
        ssc = proc_mgr.service(SparkManager).spark_streaming_context
        ssc.start()

        if self.timeout is not None:
            self.log().info('spark session started with a maximum duration of {} seconds.'.format(self.timeout))

        ssc.awaitTerminationOrTimeout(self.timeout)
        self.log().info('spark streaming session ended - some innocent java errors may appear')

        return StatusCode.Success

    def finalize(self):
        """Finalize SparkStreamingController"""

        return StatusCode.Success
