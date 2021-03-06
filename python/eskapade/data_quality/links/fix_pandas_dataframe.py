# **********************************************************************************
# * Project: Eskapade - A python-based package for data analysis                   *
# * Class  : FixPandasDataFrame                                                    *
# * Created: 2017/04/07                                                            *
# * Description:                                                                   *
# *      Link for fixing dirty pandas dataframe with inconsistent datatypes        *
# *      See example in: tutorials/esk501_fix_pandas_dataframe.py                  *
# *                                                                                *
# * Authors:                                                                       *
# *      KPMG Big Data team, Amstelveen, The Netherlands                           *
# *                                                                                *
# * Redistribution and use in source and binary forms, with or without             *
# * modification, are permitted according to the terms listed in the file          *
# * LICENSE.                                                                       *
# **********************************************************************************

import pandas as pd
import numpy as np
import re
import string
import copy
from collections import Counter
#import fastnumbers

from eskapade import ProcessManager, ConfigObject, Link, DataStore, StatusCode
from eskapade.data_quality.dq_helper import check_nan, convert, cleanup_string, CONV_FUNCS


class FixPandasDataFrame(Link):
    """Fix dirty Pandas dataframe with inconsistent datatypes

    Default settings perform the following clean-up steps on an input
    dataframe:

    - Fix all column names.  E.g. remove punctuation and strange characters,
      and convert spaces to underscores.
    - Check for various possible nans in the dataset, then make all nans
      consistent by turning them into numpy.nan (= float)
    - Per column, assess dynamically the most consistent datatype (ignoring
      all nans in that column).  E.g. bool, int, float, datetime64, string.
    - Per column, make the data types of all rows consistent, by using the
      identified (or imposed) data type (by default ignoring all nans)

    Boolean columns with contamination get converted to string columns by
    default.  Optionally, they can be converted to integer columns as well.

    The FixPandasDataFrame link can be used in a dataframe loop, in which
    case any data type assessed per column in the first dataframe iteration
    will be used for the next dataframes as well.

    The default settings should work pretty well in many circumstances, by
    can be configured pretty flexibly.  Optionally:

    - Instead of dynamically assessed, the data type can also be imposed per column
    - All nans in a column can be converted to a value consistent with the
      data type of that column.  E.g. for integer columns, nan -> -999
    - An alternative nan can be set per column and datatype
    - Modifications can be applied inplace, i.e. directly to the input dataframe
    """

    def __init__(self, **kwargs):
        """Initialize FixPandasDataFrame instance

        :param str name: name of link
        :param str read_key: key of input data to read from data store
        :param bool copy_columns_from_df: if true, copy all columns from the dataframe (default is true)
        :param list original_columns: original (unfixed) column names to pick up from input data
                                      (required if copy_columns_from_df is set to false)
        :param list contaminated_columns: (original) columns that are known to have mistakes and that
                                          should be fixed (optional)
        :param bool fix_column_names: if true, fix column names (default is true)
        :param bool strip_hive_prefix: if true, strip table-name (hive) prefix from column names,
                                       e.g. table.bla -> bla (default is false)
        :param bool convert_inconsistent_dtypes: fix column datatypes in case of data type inconsistencies in rows
                                                 (default is true)
        :param dict var_dtype: dict forcing columns to certain datatypes, e.g. {'A': int} (optional)
        :param dict var_convert_inconsistent_dtypes: dict allowing one to overwrite if certain columns
                                                     datatypes should be fixed, e.g. {'A': False} (optional)
        :param dict var_convert_func: dict with datatype conversion functions for certain columns
        :param check_nan_func: boolean return function to check for nans in columns.
                               (default is None, in which case a standard checker function gets picked up)
        :param bool convert_inconsistent_nans: if true, convert all nans to data type consistent with rest of column
                                               (default is false)
        :param dict var_convert_inconsistent_nans: dict allowing one to overwrite if certain column
                                                   nans should be fixed, e.g. {'A': False} (optional)
        :param dict var_nan: dict with nans for certain columns (optional)
        :param dict nan_dtype_map: dictionary of nans for given data types, e.g. { int: -999 }
        :param nan_default: default nan value to which all nans found get converted (default is numpy.nan)
        :param list var_bool_to_int: convert boolean column to int (default is conversion of boolean to string)
        :param bool inplace: replace original columns; overwrites store_key to read_key (default is False)
        :param str store_key: key of output data to store in data store
        :param bool drop_dup_rec: if true, drop duplicate records from data frame after other fixes (default is false)
        :param bool strip_string_columns: if true, apply strip command to string columns (default is true)
        :param list cleanup_string_columns: boolean or list. apply cleaning-up to list of selected or all string columns. 
                                            More aggressive than strip. Default is empty (= false).
        """

        # initialize Link, pass name from kwargs
        Link.__init__(self, kwargs.pop('name', 'FixPandasDataFrame'))

        # process and register all relevant kwargs. kwargs are added as attributes of the link.
        # second arg is default value for an attribute. key is popped from kwargs.
        self._process_kwargs(kwargs,
                             read_key='',
                             copy_columns_from_df=True,
                             original_columns=[],
                             contaminated_columns=[],
                             fix_column_names=True,
                             strip_hive_prefix=False,
                             convert_inconsistent_dtypes=True,
                             check_nan_func=None,
                             convert_inconsistent_nans=False,
                             var_convert_inconsistent_dtypes={},
                             var_convert_func={},
                             var_convert_inconsistent_nans={},
                             var_nan={},
                             var_dtype={},
                             var_bool_to_int=[],
                             inplace=False,
                             store_key='',
                             nan_dtype_map={},
                             nan_default=np.nan,
                             drop_dup_rec=False,
                             strip_string_columns=True,
                             cleanup_string_columns=[])

        # check residual kwargs. exit if any present.
        self.check_extra_kwargs(kwargs)

        self.fixed_columns = []

        self._var_dicts = [self.var_dtype, self.var_convert_inconsistent_dtypes,
                           self.var_nan, self.var_convert_func, self.var_convert_inconsistent_nans]
        self._df_orig_dtype = {}
        self._cnts = {}

        # set nans for individual data types
        if np.int64 not in self.nan_dtype_map:
            self.nan_dtype_map[np.int64] = -999
        if np.float64 not in self.nan_dtype_map:
            self.nan_dtype_map[np.float64] = np.nan
        if np.datetime64 not in self.nan_dtype_map:
            self.nan_dtype_map[np.datetime64] = np.datetime64('NaT')
        if str not in self.nan_dtype_map:
            self.nan_dtype_map[str] = 'not_a_str'
        if bool not in self.nan_dtype_map:
            self.nan_dtype_map[bool] = 'not_a_bool'
        if np.bool_ not in self.nan_dtype_map:
            self.nan_dtype_map[np.bool_] = self.nan_dtype_map[bool]

    def initialize(self):
        """Initialize FixPandasDataFrame"""

        self.check_arg_types(read_key=str, store_key=str)
        self.check_arg_types(recurse=True, allow_none=True, original_columns=str)
        self.check_arg_vals('read_key')

        if not isinstance(self.cleanup_string_columns, list) and not isinstance(self.cleanup_string_columns, bool):
            raise AssertionError('cleanup_string_columns should be a list of column names or boolean.')

        if self.read_key == self.store_key:
            self.inplace = True
            self.log().debug('store_key equals read_key; inplace has been set to "True"')

        if self.inplace:
            self.store_key = self.read_key
            self.log().debug('store_key has been set to read_key "%s"', self.store_key)

        if not self.store_key:
            self.store_key = self.read_key + '_fix'
            self.log().debug('store_key has been set to "%s"', self.store_key)

        # check data types
        for k in self.var_dtype.keys():
            if k not in self.contaminated_columns:
                self.contaminated_columns.append(k)
            try:
                # convert to consistent types
                dt = np.dtype(self.var_dtype[k]).type
                if dt is np.str_ or dt is np.object_:
                    dt = str
                self.var_dtype[k] = dt
            except BaseException:
                raise TypeError('unknown assigned datatype to variable "%s"' % k)

        return StatusCode.Success

    def execute(self):
        """Execute FixPandasDataFrame

        Fixing the Pandas dataframe consists of four steps:

        - Fix all column names. E.g. remove punctuation and strange characters, and convert spaces to underscores.
        - Check existing nans in that dataset, and make all nans consistent, for easy conversion later on.
        - Assess most consistent datatype for each column (ignoring all nans)
        - Make data types in each row consistent (by default ignoring all nans)
        """

        proc_mgr = ProcessManager()
        settings = proc_mgr.service(ConfigObject)
        ds = proc_mgr.service(DataStore)

        # basic checks on contensts of the data frame
        if self.read_key not in ds:
            raise KeyError('key "%s" not in DataStore' % self.read_key)
        df = ds[self.read_key]
        if not isinstance(df, pd.DataFrame):
            raise TypeError('retrieved object not of type pandas DataFrame')
        if len(df.index) == 0:
            raise AssertionError('dataframe "%s" is empty' % self.read_key)

        # use all columns from the dataframe?
        if self.copy_columns_from_df and not self.original_columns:
            self.original_columns = df.columns.tolist()
        # check not empty
        if self.original_columns:
            self.log().debug('Original columns to be processed:\n%s', str(self.original_columns))
        else:
            self.log().warning('Original columns have not been set; nothing to do')
            return StatusCode.Recoverable

        # check presence and data types of requested columns
        for col in self.original_columns:
            if col not in df.columns:
                raise AssertionError('column "%s" not present in input data frame' % (col, self.read_key))

        # set string columns to clean up
        if isinstance(self.cleanup_string_columns, bool):
            self.cleanup_string_columns = copy.copy(self.original_columns) if self.cleanup_string_columns else []

        # before we starting fixing, make a copy of the dataframe
        df_ = df if self.inplace else df.copy()

        # 1. fix column names
        self.fixed_columns = copy.copy(self.original_columns)
        if self.fix_column_names:
            regex = re.compile('[%s]' % re.escape(string.punctuation))
            all_columns = df_.columns.tolist()
            for i, col in enumerate(all_columns[:]):
                if col not in self.original_columns:
                    continue
                # strip hive prefix. eg 'tab1.foo' -> 'foo'
                new_col = col.strip()
                if self.strip_hive_prefix:
                    carr = col.split('.')
                    if len(carr) >= 2:
                        # remove prefix
                        carr.pop(0)
                    new_col = '.'.join(carr)
                # replace empty spaces
                new_col = new_col.replace(' ', '_')
                # replace punctuation
                new_col = regex.sub('_', new_col)
                # keep only alphanumeric and _
                new_col = re.sub('[^A-Za-z0-9_]+', '', new_col)
                if not new_col:
                    raise ValueError('column name "%s" empty after cleaning' % col)
                # replace column names
                all_columns[i] = new_col
                self.fixed_columns[self.fixed_columns.index(col)] = new_col
                if col in self.cleanup_string_columns:
                    self.cleanup_string_columns[self.cleanup_string_columns.index(col)] = new_col
                if col in self.var_bool_to_int:
                    self.var_bool_to_int[self.var_bool_to_int.index(col)] = new_col
                if col in self.contaminated_columns:
                    self.contaminated_columns[self.contaminated_columns.index(col)] = new_col
                for vd in self._var_dicts:
                    if col in vd:
                        vd[new_col] = vd.pop(col)
            df_.columns = all_columns
            self.log().debug('Fixed column names are:\n%s', str(self.fixed_columns))

        # --- Next: fix datatypes - all rows in a column get consistent datatype, except for nans

        # convert all values to real numbers if possible
        #df_ = df_.apply(fastnumbers.fast_real)

        # init - assess data types of columns as earlier assessed by pandas
        for col in self.fixed_columns:
            if col in self._df_orig_dtype:
                continue
            # convert to consistent types
            dt = df_[col].dtype.type
            if dt is np.str_ or dt is np.object_:
                dt = str
            self._df_orig_dtype[col] = dt

        # 2. make all nans consistent, for easy conversion later on
        #    check on nans
        n_df = len(df_.index)
        is_nan = pd.DataFrame(index=df_.index)
        check_nan_func = check_nan if not self.check_nan_func else self.check_nan_func
        for col in self.fixed_columns:
            is_nan[col] = df_[col].apply(check_nan_func)
            n_nan = is_nan[col].values.sum()
            if n_nan:
                self.log().debug('Column "%s" contains %d NaNs out of %d', col, n_nan, n_df)
            dt = self._df_orig_dtype[col]
            # np.nan is a float, so for non-floats nan is considered contamination by pandas
            if n_nan and dt is not np.float64:
                if col not in self.contaminated_columns:
                    self.contaminated_columns.append(col)
        df_[is_nan] = self.nan_default

        # 3. multiple datatypes in columns besides nans?
        #    find most common one per column
        keep = is_nan == False
        for col in self.fixed_columns:
            if col in self.var_dtype:
                continue
            df_[col] = df_[col].apply(convert)  # fastnumbers.fast_real) #convert)
            dfcol = df_[col][keep[col]]
            dtype_cnt = Counter(dfcol.apply(type).value_counts().to_dict())
            # for bookkeeping
            self._cnts[col] = dtype_cnt
            if len(dtype_cnt) == 0:
                # column contains only nans!
                if col not in self.var_dtype:
                    # stick to dtype as determined by pandas (= float)
                    self.var_dtype[col] = self._df_orig_dtype[col]
                continue
            # store most common datatype
            # first convert to consistent types
            dtype_lst = list(dtype_cnt.keys())
            for dtp in dtype_lst:
                ndt = np.dtype(dtp).type
                if ndt is np.str_ or ndt is np.object_:
                    ndt = str
                mc = dtype_cnt.pop(dtp)
                dtype_cnt[ndt] += mc
            prefered_dtype = determine_preferred_dtype(dtype_cnt)
            if col not in self.var_dtype:
                self.var_dtype[col] = prefered_dtype
            if len(dtype_cnt) > 1:
                self.log().warning('Found multiple types for column "%s"', col)
                self.log().debug('Picked type "%s" for column "%s" (counts: %s)', prefered_dtype, col, str(dtype_cnt))
                if col not in self.contaminated_columns:
                    self.contaminated_columns.append(col)

        self.log().debug('Consider setting link.var_dtype = %s', str(self.var_dtype))
        self.log().info('Fixing contamination in columns %s',
                        ', '.join('"{}"'.format(c) for c in self.contaminated_columns))

        # 4. fix contamination in each column
        for col in self.contaminated_columns:
            dt = self.var_dtype[col]
            self.log().debug('Converting rows in column "%s" to type "%s"', col, dt)
            # pick conversion function of choice
            if col in self.var_convert_func:
                fnc = self.var_convert_func[col]
            elif col in self.var_bool_to_int:
                fnc = bool_to_int
            elif dt in CONV_FUNCS:
                fnc = CONV_FUNCS[dt]
            else:
                raise RuntimeError('Do not know how to convert column "%s"' % col)
            # convert inconsistent dtypes?
            convert_inconsistent_dtypes = self.var_convert_inconsistent_dtypes[
                col] if col in self.var_convert_inconsistent_dtypes else self.convert_inconsistent_dtypes
            convert_inconsistent_nans = self.var_convert_inconsistent_nans[
                col] if col in self.var_convert_inconsistent_nans else self.convert_inconsistent_nans
            fnc_kw = {}
            fnc_kw['convert_inconsistent_dtypes'] = convert_inconsistent_dtypes
            # pick nan of choice
            if col in self.var_nan:
                fnc_kw['nan'] = self.var_nan[col]
                if convert_inconsistent_nans:
                    rdt = dt if col not in self.var_bool_to_int else np.int64
                    if not isinstance(self.var_nan[col], rdt):
                        fnc_kw['nan'] = self.nan_dtype_map[rdt]
                        self.log().warning('Chosen nan for col "%s" not of type "%s"; reverting to default nan: "%s"',
                                           col, rdt, self.nan_dtype_map[dt])
            else:
                if convert_inconsistent_nans:
                    fnc_kw['nan'] = self.nan_dtype_map[dt]
                else:
                    fnc_kw['nan'] = self.nan_default
            # apply dtype fix here
            df_[col] = df_[col].apply(fnc, **fnc_kw)

        if self.drop_dup_rec:
            # drop duplicate records
            df_.drop_duplicates(inplace=True)

        # cleaning up of string columns (1/2)
        if self.strip_string_columns:
            # strip string based columns
            for col, dt in self.var_dtype.items():
                if dt != str and dt != np.str_:
                    continue
                df_[col] = df_[col].str.strip()

        # cleaning up of string columns (2/2)
        if self.cleanup_string_columns:
            # strip string based columns
            for col, dt in self.var_dtype.items():
                if dt != str and dt != np.str_:
                    continue
                df_[col] = df_[col].apply(cleanup_string)

        # storage
        ds[self.store_key] = df_

        return StatusCode.Success


def determine_preferred_dtype(dtype_cnt):
    """Determine preferred column data type"""

    # get sorted type counts for column
    type_cnts = dtype_cnt.most_common()
    if not type_cnts:
        return None

    # determine preferred type from types with the highest count
    type_order = {str: '0', np.float64: '1', np.int64: '2', np.bool_: '3'}
    return sorted((cnt[0] for cnt in type_cnts if cnt[1] == type_cnts[0][1]),
                  key=lambda t: type_order.get(t, t.__name__))[0]
