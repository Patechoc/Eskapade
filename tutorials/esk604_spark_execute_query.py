# ********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                 *
# * Macro  : esk604_spark_execute_query                                          *
# * Created: 2017/06/07                                                          *
# * Description:                                                                 *
# *     Tutorial macro for applying a SQL-query to one more objects in the       *
# *     DataStore. Such SQL-queries can for instance be used to filter data.     *
# *                                                                              *
# * Redistribution and use in source and binary forms, with or without           *
# * modification, are permitted according to the terms listed in the file        *
# * LICENSE.                                                                     *
# ********************************************************************************

import logging
log = logging.getLogger('macro.esk604_spark_execute_query')

from eskapade import ConfigObject, ProcessManager
from eskapade.core import persistence
from eskapade.spark_analysis import SparkManager
from eskapade import spark_analysis

log.debug('Now parsing configuration file esk604_spark_execute_query')


##########################################################################
# Minimal analysis information

proc_mgr = ProcessManager()

settings = proc_mgr.service(ConfigObject)
settings['analysisName'] = 'esk604_spark_execute_query'
settings['version'] = 0


##########################################################################
# Start Spark session

spark = proc_mgr.service(SparkManager).create_session(eskapade_settings=settings)


##########################################################################
# CSV and dataframe settings

# NB: local file may not be accessible to worker node in cluster mode
file_paths = ['file:' + persistence.io_path('data', settings.io_conf(), 'dummy1.csv'),
              'file:' + persistence.io_path('data', settings.io_conf(), 'dummy2.csv')]

# define store_key for all data files to be read in
STORE_KEYS = ['spark_df1', 'spark_df2']

##########################################################################
# Now set up the chains and links based on configuration flags

proc_mgr.add_chain('Read')

# create read link for each data file
for index, key in enumerate(STORE_KEYS):
    read_link = spark_analysis.SparkDfReader(name='Reader' + str(index + 1),
                                             store_key=key,
                                             read_methods=['csv'])

    # set CSV read arguments
    read_link.read_meth_args['csv'] = (file_paths[index],)
    read_link.read_meth_kwargs['csv'] = dict(sep='|', header=True, inferSchema=True)

    # add link to chain
    proc_mgr.get_chain('Read').add_link(read_link)


# create SQL-query link
sql_link = spark_analysis.SparkExecuteQuery(name='SparkSQL',
                                            store_key='spark_df_sql')

# define SQL-query to apply to one or more objects in the DataStore
sql_link.query = 'SELECT loc, sum(x) as sumx, sum(y) as sumy ' \
                 'FROM (SELECT * FROM {0:s} UNION ALL SELECT * FROM {1:s}) t ' \
                 'WHERE t.x < 5 ' \
                 'GROUP BY loc'.format(STORE_KEYS[0], STORE_KEYS[1])

# add link to chain
proc_mgr.add_chain('ApplySQL').add_link(sql_link)


##########################################################################

log.debug('Done parsing configuration file esk604_spark_execute_query')
