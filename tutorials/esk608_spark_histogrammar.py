# ********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                 *
# * Macro  : esk608_spark_histogrammar                                           *
# * Created: 2017/05/31                                                          *
# * Description:                                                                 *
# *     Tutorial macro for making histograms of a spark dataframe                *
# *                                                                              *
# * Redistribution and use in source and binary forms, with or without           *
# * modification, are permitted according to the terms listed in the file        *
# * LICENSE.                                                                     *
# ********************************************************************************

import logging
import os
import pyspark
log = logging.getLogger('macro.esk608_spark_histogrammar')

from eskapade import ConfigObject, ProcessManager, visualization
from eskapade.core import persistence
from eskapade import spark_analysis
from eskapade.spark_analysis import SparkManager

log.debug('Now parsing configuration file esk608_spark_histogrammar')


##########################################################################
# --- minimal analysis information

proc_mgr = ProcessManager()

settings = proc_mgr.service(ConfigObject)
settings['analysisName'] = 'esk608_spark_histogrammar'
settings['version'] = 0


##########################################################################
# --- start Spark session

spark = proc_mgr.service(SparkManager).create_session(eskapade_settings=settings)


##########################################################################
# --- CSV and data-frame settings

file_paths = ['file:' + persistence.io_path('data', settings.io_conf(), 'dummy.csv')]
separator = '|'
has_header = True
infer_schema = True
num_partitions = 4
columns = ['date', 'loc', 'x', 'y']


##########################################################################
# --- now set up the chains and links based on configuration flags

# create read link
read_link = spark_analysis.SparkDfReader(name='Reader',
                                         store_key='spark_df',
                                         read_methods=['csv'])

# set CSV read arguments
read_link.read_meth_args['csv'] = (file_paths,)
read_link.read_meth_kwargs['csv'] = dict(sep=separator,
                                         header=has_header,
                                         inferSchema=infer_schema)

if columns:
    # add select function
    read_link.read_methods.append('select')
    read_link.read_meth_args['select'] = tuple(columns)

if num_partitions:
    # add repartition function
    read_link.read_methods.append('repartition')
    read_link.read_meth_args['repartition'] = (num_partitions,)

# add link to chain
proc_mgr.add_chain('Read').add_link(read_link)


ch = proc_mgr.add_chain('Output')


# fill spark histograms
hf = spark_analysis.SparkHistogrammarFiller()
hf.read_key = read_link.store_key
hf.store_key = 'hist'
hf.set_log_level(logging.DEBUG)
# colums that are picked up to do value_counting on in the input dataset
# note: can also be 2-dim: ['x','y']
# in this example, the rest are one-dimensional histograms
hf.columns = ['x', 'y', 'loc', ['x', 'y'], 'date']
ch.add_link(hf)


# make a nice summary report of the created histograms
hist_summary = visualization.DfSummary(name='HistogramSummary',
                                       read_key=hf.store_key)
ch.add_link(hist_summary)


###########################################################################
# --- the end

log.debug('Done parsing configuration file esk608_spark_histogrammar')
