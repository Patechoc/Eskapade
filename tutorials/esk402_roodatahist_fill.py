# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Macro  : esk402_roodatahist_fill                                             *
# * Created: 2017/03/28                                                            *
# *                                                                                *
# * Description:
# *
# * This macro illustrates how to fill a N-dimensional roodatahist from a 
# * pandas dataframe. (A roodatahist can be filled iteratively, while looping
# * over multiple pandas dataframes.) The roodatahist can be used to create
# * a roofit histogram-pdf (roohistpdf).
# * 
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Licence:
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

import logging
log = logging.getLogger('macro.esk402_roodatahist_fill')

from eskapade import ConfigObject, ProcessManager
from eskapade import core_ops, analysis, root_analysis

log.debug('Now parsing configuration file esk402_roodatahist_fill')

#########################################################################################
# --- minimal analysis information

proc_mgr = ProcessManager()

settings = proc_mgr.service(ConfigObject)
settings['analysisName'] = 'esk402_roodatahist_fill'
settings['version'] = 0

#########################################################################################
# --- Analysis values, settings, helper functions, configuration flags.

input_files = [os.environ['ESKAPADE'] + '/data/mock_accounts.csv.gz']

#########################################################################################
# --- now set up the chains and links based on configuration flags

ch = proc_mgr.add_chain('Data')

# --- 0. readdata keeps on opening the next file in the file list.
#     all kwargs are passed on to pandas file reader.
readdata = analysis.ReadToDf(name='dflooper', key='accounts', reader='csv')
readdata.path = input_files
#readdata.itr_over_files = True
ch.add_link(readdata)

# --- 1. add the record factorizer to convert categorical observables into integers
#     Here the columns dummy and loc of the input dataset are factorized
#     e.g. x = ['apple', 'tree', 'pear', 'apple', 'pear'] becomes the column:
#     x = [0, 1, 2, 0, 2]
#     By default, the mapping is stored in a dict under key: 'map_'+store_key+'_to_original'
fact = analysis.RecordFactorizer(name='rf1')
fact.columns = ['isActive', 'eyeColor', 'favoriteFruit', 'gender']
fact.read_key = 'accounts'
fact.inplace = True
# factorizer stores a dict with the mappings that have been applied to all observables
fact.sk_map_to_original = 'to_original'
# factorizer also stores a dict with the mappings back to the original observables
fact.sk_map_to_factorized = 'to_factorized'
fact.set_log_level(logging.DEBUG)
ch.add_link(fact)

# --- 2. Fill a roodatahist
df2rdh = root_analysis.RooDataHistFiller()
df2rdh.read_key = readdata.key
df2rdh.store_key = 'rdh_' + readdata.key
# the observables in this map are treated as categorical observables by roofit (roocategories)
df2rdh.map_to_factorized = 'to_factorized'
df2rdh.columns = ['transaction', 'latitude', 'longitude', 'age', 'eyeColor', 'favoriteFruit']
#df2rdh.into_ws = True
ch.add_link(df2rdh)

# --- print contents of the datastore
proc_mgr.add_chain('Overview')
pds = core_ops.PrintDs()
pds.keys = ['n_rdh_accounts', 'n_accounts']
proc_mgr.get_chain('Overview').add_link(pds)

#########################################################################################

log.debug('Done parsing configuration file esk402_roodatahist_fill')
