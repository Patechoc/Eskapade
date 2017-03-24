import numpy as np
import pandas as pd
import random
from collections import Counter
from sortedcontainers import SortedDict

from eskapade.core.mixins import ArgumentsMixin, LoggingMixin

###################
# histogram tools #
###################


def _check_num_vals(cnts_iter):
    """ Check that all values in provided array are numeric.

    :raises TypeError: if any non-numeric type is found in input array.
    """

    non_num = False
    for val in cnts_iter:
        if isinstance(val, str):
            non_num = True
            break
        try:
            float(val)
        except:
            non_num = True
            break
    if non_num:
        raise TypeError('non-numeric type found ("%s")' % type(val).__name__)


class ValueCounts(object):
    """ The class ValueCounts contains a dictionary of value counts.

    The dictionary of value counts comes out of pandas.series.value_counts()
    for one variable or pandas.Dataframe.groupby.size() performed over one or
    multiple variables.
    """

    def __init__(self, key, subkey=None, counts={}, sel={}):
        """ Initialize the ValueCounts object.

        :param list key: key is a tuple, list or string of (the) variable name(s), matching those and the structure of
        the keys in the value_counts dictionary.
        :param dict counts: the value_counts dictionary.
        :param list subkey: subset of key. If provided, the value_counts dictionary will be projected from key onto the (subset of) subkey.
        E.g. use this to map a two dimensional value_counts dictionary onto one specified dimension. Default is None. Optional.
        :param dict sel: Apply selections to value_counts dictionary. Default is {}. Optional.
        """
        key = self._transform_key(key)
        subkey = self._transform_key(subkey)
        counts = dict((k if isinstance(k, tuple) else (k,), v)
                      for k, v in counts.items())

        self._key = key
        self._skey = subkey if subkey is not None else key
        self._cnts = counts
        self._sel = dict((k, list(s) if hasattr(s, '__iter__')
                          else [s]) for k, s in sel.items())
        self._ktos = tuple(key.index(k) for k in subkey)
        self._kind = dict((k, key.index(k)) for k in key)
        self._stok = tuple(
            subkey.index(k) if k in subkey else None for k in key)
        self._no_none_cnts = SortedDict()

    def __lt__(self, other):
        """ Lesser than operator

        :param object other: the other ValueCounts object
        :returns: true or false.
        :rtype: bool
        """
        return len(self._key) < len(other._key)

    def __gt__(self, other):
        """ Greater than operator

        :param object other: the other ValueCounts object
        :returns: true or false.
        :rtype: bool
        """
        return len(self._key) > len(other._key)

    def __eq__(self, other):
        """ Is equal operator

        :param object other: the other ValueCounts object
        :returns: true or false.
        :rtype: bool
        """
        return len(self._key) == len(other._key) and tuple(
            self._skey) == tuple(other._skey)

    def __le__(self, other):
        """ Lesser or equal operator

        :param object other: the other ValueCounts object
        :returns: true or false.
        :rtype: bool
        """
        return self.__lt__(other) or self.__eq__(other)

    def __ge__(self, other):
        """ Greater or equal operator

        :param object other: the other ValueCounts object
        :returns: true or false.
        :rtype: bool
        """
        return self.__lt__(other) or self.__eq__(other)

    def _transform_key(self, key):
        """ Transform input key to desired tuple format.

        Input key, a tuple, list, or string, gets transformed into the desired key formay.
        Desired key format is a tuple like this:

        * ('foo',) : for one variable (note the comma),
        * ('foo','bar') : for multiple variables.

        This format follows the same structure of the keys used in the internal value_counts dictionary.

        :param tuple key: input key, is a tuple, list, or string
        :returns: the tuplelized key
        :rtype: tuple
        """
        assert len(
            key), 'Input key contains no variable name(s). Expect str or tuple or list of strings.'

        has_itr = isinstance(key, list) or isinstance(key, tuple)
        if has_itr:
            if len(key) == 1:
                key = (key[0],)
            else:
                key = tuple(key)
        elif isinstance(key, str):
            key = (key,)
        else:
            # don't recognize the key! pass.
            pass
        return key

    @property
    def counts(self):
        """ Return the value_counts dictionary.

        :returns: after processing, returns the value_counts dictionary
        :rtype: dict
        """
        self.process_counts()
        return self._cnts

    @property
    def nononecounts(self):
        """ Return the value_counts dictionary without None keys.

        :returns: after processing, returns the value_counts dictionary without None keys
        :rtype: dict
        """
        self.process_counts()
        if len(self._no_none_cnts) == 0:
            self._no_none_cnts = SortedDict(
                [(var, cnt) for var, cnt in self._cnts.items() if None not in var])
        # return dict([(var, cnt) for var, cnt in self._cnts.items() if None
        # not in var])
        return self._no_none_cnts

    @property
    def key(self):
        """
        Return the (current) key of ValueCounts object.

        :returns: the key
        :rtype: tuple
        """
        self.process_counts()
        return self._key

    @property
    def skey(self):
        """
        Return the (current) subkey of ValueCounts object.

        :returns: the subkey
        :rtype: tuple
        """
        return self._skey

    @property
    def num_bins(self):
        """
        Return the number of bins in the ValueCounts object.

        :returns: number of bins
        :rtype: int
        """
        return len(self.counts)

    @property
    def num_nonone_bins(self):
        """
        Return the number of not-none bins in the ValueCounts object.

        :returns: number of not-none bins
        :rtype: int
        """
        return len(self.nononecounts)

    @property
    def sum_counts(self):
        """
        Return the sum of counts of all bins in the ValueCounts object.

        :returns: the sum of counts of all bins
        :rtype: float
        """
        return sum(self._cnts.values())

    @property
    def sum_nonone_counts(self):
        """
        Return the sum of not-none counts of all bins in the ValueCounts object.

        :returns: the sum of not-none counts of all bins
        :rtype: float
        """
        return sum(self.nononecounts.values())

    def create_sub_counts(self, subkey, sel={}):
        """
        Project the existing value_counts dict onto a subset of keys.

        E.g. map variables x,y onto single dimension x, so for each bin in x integrate over y.

        :param tuple subkey: input sub-key, is a tuple, list, or string. This is the new key of variables for the returned ValueCounts object.
        :param dict sel: dictionary with selection. Default is {}.
        :returns: value_counts object where subkey has become the new key.
        :rtype: ValueCounts
        """
        subkey = self._transform_key(subkey)
        return ValueCounts(self.key, subkey, self.counts, sel)

    def count(self, value_bin):
        """ Get bin count for specific bin-key value_bin.

        :param tuple value_bin: a specific key, and can be a list or tuple.
        :returns: specific bin counter value
        :rtype: int
        """
        self.process_counts()
        return self._cnts.get(tuple(value_bin[k] for k in self._stok), 0)

    def get_values(self, val_keys=()):
        """ Get all key-values of a subset of keys.

        E.g. give all x values in of the keys, when the value_counts object has keys (x,y).

        :param tuple value_keys: a specific sub-key to get key values for.
        :returns: all key-values of a subset of keys.
        :rtype: tuple
        """
        self.process_counts()
        if not val_keys:
            val_keys = self._skey
        return sorted(set(tuple(key[self._kind[k]]
                                for k in val_keys) for key in self._cnts.keys()))

    def remove_keys_of_inconsistent_type(self, prefered_key_type=None):
        """ Remove all keys that have inconsistent data type(s)

        :param tuple prefered_key_type: the prefered key type to keep. Can be a tuple, list, or single type. E.g. str or (int,str,float).
        If None provided, the most common key type found is kept.
        """
        self.process_counts()

        # NB: np.dtype(type(k).type : gives back a consistent numpy type for
        # all strings, floats, ints, etc.

        # convert prefered_key_type to right format
        if prefered_key_type is not None:
            #has_itr = hasattr(prefered_key_type, '__iter__')
            has_itr = isinstance(
                prefered_key_type,
                list) or isinstance(
                prefered_key_type,
                tuple)

            if has_itr:
                if len(prefered_key_type) == 1:
                    prefered_key_type = (prefered_key_type[0],)
                else:
                    prefered_key_type = tuple(prefered_key_type)
            else:
                prefered_key_type = (prefered_key_type,)
            # turn into consistent types, used for comparison below
            prefered_key_type = tuple(
                np.dtype(k).type for k in prefered_key_type)

        # sort all keys by their key type, and count how often these types
        # occur
        cnts_types = Counter()
        cnts_keys = dict((tuple(np.dtype(type(k)).type for k in key), [])
                         for key in self._cnts)
        for key in self._cnts:
            ktype = tuple(np.dtype(type(k)).type for k in key)
            cnts_types[ktype] += self._cnts[key]
            cnts_keys[ktype].append(key)

        # pick the prefered key type to keep
        if prefered_key_type is None:
            # select most common key type
            prefered_key_type = cnts_types.most_common()[0][0]

        # remove all keys of different key type than preferred
        for ktype in cnts_types:
            if ktype == prefered_key_type:
                continue
            keys = cnts_keys[ktype]
            for k in keys:
                del self._cnts[k]

        # no_none_cnts gets refilled next time when called
        self._no_none_cnts.clear()

    def process_counts(self, accept_equiv=True):
        """
        Project the existing value_counts dict onto the existing subset of keys.

        E.g. map variables x,y onto single dimension x, so for each bin in x integrate over y.

        :param bool accept_equiv: accept equivalence of key and subkey if if subkey is in different order than key. Default is true.
        :returns: successful projection or not
        :rtype: bool
        """
        # only process if counts need processing
        if not self._sel and self._key == self._skey:
            return False
        if not self._sel and accept_equiv and all(
                k in self._skey for k in self._key):
            return False

        # create new counts dictionary with subcounts
        scnts = {}
        for vals, cnt in self._cnts.items():
            # apply selection
            if self._sel and any(vals[self._kind[k]]
                                 not in s for k, s in self._sel.items()):
                continue

            # add counts for subkey to sum
            vkey = tuple(vals[i] for i in self._ktos)
            if vkey not in scnts:
                scnts[vkey] = 0
            scnts[vkey] += cnt

        # set subcounts as new counts
        self._key = self._skey
        self._cnts = scnts
        self._sel = {}
        self._kind = dict((k, self._key.index(k)) for k in self._key)
        self._ktos = self._stok = tuple(range(len(self._skey)))
        # no_none_cnts refilled when called
        self._no_none_cnts.clear()
        return True


class BinningUtil(object):
    """ BinningUtil is a helper class used for interpreting bin specification dictionaries.

    BinningUtil is a base class for the Histogram class.
    """

    def __init__(self, **kwargs):
        """ Initialization of the BinningUtil class.

        A bin_specs dictionary needs to be provided as input. bins_specs is a dict containing 'bin_width' and 'bin_offset' keys.
        In case bins widths are not equal, bin_specs contains 'bin_edges' (array) instead of 'bin_width' and 'bin_offset'.
        'bin_width' and 'bin_offset' can be numeric or numpy timestamps.

        Alternatively, bin_edges can be provided as input to bin_specs.

        Example bin_specs dictionaries are:

        >>> bin_specs = { 'bin_width': 1, 'bin_offset': 0 }
        >>> bin_spect = { 'bin_edges': [0,2,3,4,5,7,8] }
        >>> bin_specs = { 'bin_width': np.timedelta64(30,'D'), \
                          'bin_offset': np.datetime64('2010-01-04') }

        :param dict bin_specs: dictionary contains 'bin_width' and 'bin_offset' numbers or 'bin_edges' array. Default is None.
        :param list bin_edges: array with numpy histogram style bin_edges. Default is None.
        """
        bin_specs = kwargs.pop('bin_specs', None)
        bin_edges = kwargs.pop('bin_edges', None)

        if bin_specs is not None:
            self.bin_specs = bin_specs
        elif bin_edges is not None:
            assert isinstance(bin_edges, list), 'bin_edges should be a list.'
            self.bin_specs = {'bin_edges': bin_edges}
        else:
            self.bin_specs = {}

        # check bin specifications
        if self.bin_specs:
            assert isinstance(
                self.bin_specs, dict), 'bin_specs should be a dictionary.'
            assert any(k in self.bin_specs for k in ['bin_edges', 'bin_width']), \
                'unable to interpret bin specifications: %s' % self.bin_specs
            if 'bin_edges' in self.bin_specs and 'bin_width' in self.bin_specs:
                raise RuntimeError(
                    'both bin edges and bin width specified for histogram')

    @property
    def bin_specs(self):
        """
        Get bin_specs dictionary.

        :returns: bin_specs dictionary
        :rtype: dict
        """
        return dict(self._bin_specs)

    @bin_specs.setter
    def bin_specs(self, specs):
        """
        Set bin_specs dictionary.

        :param dict bin_specs: dictionary contains 'bin_width' and 'bin_offset' numbers or 'bin_edges' array.
        :raises RunTimeError: If bin_specs already exists, it will not overwrite.
        """
        if hasattr(self, '_bin_specs'):
            raise RuntimeError('histogram bin specifications already set')
        self._bin_specs = dict(specs)

    def value_to_bin_label(self, var_value, greater_equal=False):
        """
        Return the bin index that belongs to a certain bin value.

        :param var_value: variable value for which to find the bin index.
        :param bool greater_equal: for float, int, timestamp, return index of bin for which value falls in range [lower edge, upper edge).
        If set to true, return index of bin for which value falls in range [lower edge, upper edge]. Default if false.
        :returns: bin index
        :rtype: int
        """
        # check bin specifications and specified value
        if not self.bin_specs:
            return None
        # NOTE: lines below also work with timestamps. Order is important!
        # find bin label
        if 'bin_width' in self.bin_specs:
            return int(np.floor(
                (var_value - self.bin_specs.get('bin_offset', 0)) / self.bin_specs['bin_width']))
        if var_value <= self.bin_specs['bin_edges'][0]:
            return 0
        elif var_value >= self.bin_specs['bin_edges'][-1]:
            return len(self.bin_specs['bin_edges']) - 2
        for i, be in enumerate(self.bin_specs['bin_edges'][1:]):
            if greater_equal:
                if be >= var_value:
                    return i
            else:
                if be > var_value:
                    return i

    def get_bin_center(self, bin_label):
        """
        Return the bin center that belongs to a certain bin index.

        :param bin_label: bin label for which to find the bin center.
        :returns: bin center, can be float, int, timestamp
        """
        if not self.bin_specs:
            return None
        bin_idx = np.int64(bin_label)
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            assert bin_idx >= 0 and bin_idx < len(bin_edges), \
                'ERROR. bin_label <%s> does not fit in bin_edges.' % bin_label
            # NOTE: computation below also works with timestamps! Order is
            # important.
            bin_width = bin_edges[bin_idx + 1] - bin_edges[bin_idx]
            bin_width_half = bin_width / 2.
            bin_center = bin_edges[bin_idx] + bin_width_half
        else:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0.)
            # NOTE: this notation also works with timestamps!
            bin_center = offset + (bin_idx + 0.5) * width
        return bin_center

    def get_left_bin_edge(self, bin_label):
        """ Return the left bin edge that belongs to a certain bin index.

        :param bin_label: bin label for which to find the left bin edge.
        :returns: bin edge, can be float, int, timestamp
        """
        # check bin specifications and specified value
        if not self.bin_specs:
            return None
        bin_idx = np.int64(bin_label)
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            assert bin_idx >= 0 and bin_idx < len(bin_edges), \
                'ERROR. bin_label <%s> does not fit in bin_edges.' % bin_label
            bin_edge_left = bin_edges[bin_idx]
        else:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0.)
            # NOTE: this notation also works with timestamps!
            bin_edge_left = offset + (bin_idx * width)
        return bin_edge_left

    def get_right_bin_edge(self, bin_label):
        """ Return the right bin edge that belongs to a certain bin index.

        :param bin_label: bin label for which to find the right bin edge.
        :returns: bin edge, can be float, int, timestamp
        """
        # check bin specifications and specified value
        if not self.bin_specs:
            return None
        bin_idx = np.int64(bin_label)
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            assert bin_idx >= 0 and bin_idx < len(bin_edges) - 1, \
                'ERROR. bin_label <%s> does not fit in bin_edges.' % bin_label
            bin_edge_right = bin_edges[bin_idx + 1]
        else:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0.)
            # NOTE: this notation also works with timestamps!
            bin_edge_right = offset + (bin_idx + 1) * width
        return bin_edge_right

    def get_bin_edges(self):
        """ Return the bin edges.

        :returns: bin edges
        :rtype: array
        """
        if not self.bin_specs:
            return None
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
        else:
            bin_edges = None
        return bin_edges

    def get_bin_edges_range(self):
        """ Return the bin range determined from bin_edges.

        :returns: bin range
        :rtype: tuple
        """
        if not self.bin_specs:
            return None
        if 'bin_edges' in self.bin_specs:
            return (self.bin_specs['bin_edges'][0],
                    self.bin_specs['bin_edges'][-1])
        else:
            return None

    def truncated_bin_edges(self, variable_range=[]):
        """ Bin edges corresponding to a given variable range.

        :param list variable_range: variable range used for finding the right bin edges array.
        :returns: truncated bin edges
        :rtype: array
        """
        # check type of input arguments
        variable_range = tuple(variable_range)

        # trivial cases
        if not variable_range:
            return self.get_bin_edges()
        if not self.bin_specs:
            return np.array(variable_range)

        # check specified value range
        ttest = False
        try:
            if isinstance(variable_range[0], str) or isinstance(
                    variable_range[1], str):
                ttest = True
        except:
            ttest = True
        if ttest or not len(variable_range) == 2 or variable_range[
                1] <= variable_range[0]:
            raise RuntimeError('expected a variable range (min, max); got "%s"',
                               str(variable_range))
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            if variable_range[
                    0] > bin_edges[-1] or variable_range[1] <= bin_edges[0]:
                raise RuntimeError('expected a minimum and a maximum in histogram range (min, max); got "%s"',
                                   str(variable_range))
                raise RuntimeError('expected a minimum and a maximum in histogram range (%s, %s); got "%s"',
                                   bins[0], bins[-1], str(variable_range))

        # on to the non-trivial cases
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']

            min_idx = self.value_to_bin_label(variable_range[0])
            # if variable_range[1] is on a bin-edge, make sure we keep
            # the previous bin's right edge.
            max_idx = self.value_to_bin_label(
                variable_range[1], greater_equal=True)
            bins = np.asarray(bin_edges[min_idx:max_idx + 2])
            bins = bins.tolist()
        else:
            try:
                bin_width = self.bin_specs['bin_width']
                bin_offset = self.bin_specs['bin_offset']
            except:
                raise NotImplementedError(
                    'No bin_width and/or bin_offset in bin_specs')

            min_idx = self.value_to_bin_label(variable_range[0])
            # if variable_range[1] is on a bin-edge, make sure we keep
            # the previous bin's right edge.
            max_idx = self.value_to_bin_label(
                variable_range[1], greater_equal=True)
            bins = variable_range = (
                self.get_left_bin_edge(min_idx),
                self.get_right_bin_edge(max_idx))

            # ensure to include right edge for highest bin
            bins = np.arange(
                variable_range[0],
                variable_range[1] +
                0.5 *
                bin_width,
                bin_width)
            bins = bins.tolist()

        return bins


class Histogram(BinningUtil, ArgumentsMixin, LoggingMixin):
    """
    Generic 1D Histogram class.

    Histogram holds bin labels (name of each bin), value_counts (values of the histogram) and a
    variable name. The bins can be categoric or numeric, where numeric includes timestamps.
    In case of numeric bins, bin_specs is set. bins_specs is a dict containing bin_width and bin_offset.
    In case bins widths are not equal, bin_specs contains bin_edges instead of bin_width and bin_offset.
    """

    def __init__(self, counts, **kwargs):
        """
        A bin_specs dictionary can be provided as input. bins_specs is a dict containing 'bin_width' and 'bin_offset' keys.
        In case bins widths are not equal, bin_specs contains 'bin_edges' (array) instead of 'bin_width' and 'bin_offset'.
        'bin_width' and 'bin_offset' can be numeric or numpy timestamps.

        Example bin_specs dictionaries are:

        >>> bin_specs = { 'bin_width': 1, 'bin_offset': 0 }
        >>> bin_spect = { 'bin_edges': [0,2,3,4,5,7,8] }
        >>> bin_specs = { 'bin_width': np.timedelta64(30,'D'), \
                          'bin_offset': np.datetime64('2010-01-04') }

        :param object counts: Can be a ValueCounts object, dict or tuple.
            * tuple: Histogram((bin_values, bin_edges), variable=<your_variable_name>)
            * dict: a dictionary as comes out of pandas.series.value_counts() or pandas.Dataframe.groupby.size() over one variable.
            * ValueCounts: a ValueCounts object contains a value_counts dictionary.
        :param dict bin_specs: dictionary contains 'bin_width' and 'bin_offset' numbers or 'bin_edges' array. Default is None.
        :param str variable: Name of the variable represented by the histogram.
        :param type datatype: data type of the variable represented by the histogram. Optional.
        """
        # initialize Binning, pass bin_specs from kwargs
        BinningUtil.__init__(self, bin_specs=kwargs.pop('bin_specs', None))

        # parse arguments
        self._process_kwargs(kwargs, variable='', datatype=None)
        self.check_arg_vals('variable')
        self.check_arg_types(variable=str, bin_specs=dict)

        # check for extraneous keyword arguments
        self.check_extra_kwargs(kwargs)

        self.log().debug('initializing histogram for "%s"', self.variable)

        # set value counts
        if isinstance(counts, ValueCounts):
            # from ValueCounts object
            self._from_value_counts(counts)
        elif isinstance(counts, dict):
            # from value-counts dictionary
            self._from_dict(counts)
        else:
            # try from NumPy-style histogram
            try:
                counts, var_vals = list(counts[0]), list(counts[1])
            except:
                self.log().critical(
                    'invalid type for specified counts: "%s"',
                    type(counts).__name__)
                raise RuntimeError('invalid type for specified counts')
            self._from_numpy(counts, var_vals)

        # remove inconsistent keys. Do this before nonone_bins dict is created,
        # which required sortable (= consistent) keys
        self.remove_keys_of_inconsistent_type()
            
        # check counts
        if self._val_counts.num_nonone_bins < 1:
            self.log().critical('no bin counts specified for "%s"', self.variable)
            raise RuntimeError('no bin counts specified')

        # check bin specifications
        if self.bin_specs:
            if 'bin_width' in self.bin_specs:
                try:
                    _check_num_vals(self.get_bin_labels())
                except TypeError as exc:
                    self.log().critical('non-numeric values in bin labels not allowed if bin width is specified: %s',
                                        self.get_bin_labels())
                    raise exc
            elif 'bin_edges' in self.bin_specs:
                edges = self.bin_specs['bin_edges']
                if len(edges) != self._val_counts.num_nonone_bins + 1:
                    self.log().critical('number of specified bin edges (%d) does not match number of bins (%d)',
                                        len(edges), self._val_counts.num_nonone_bins)
                    raise RuntimeError(
                        'numbers of bins and bin edges do not match')
                try:
                    _check_num_vals(edges)
                except TypeError as exc:
                    self.log().critical('non-numeric values found in bin edges: %s', edges)
                    raise exc
                if any(e2 <= e1 for e1, e2 in zip(edges[:-1], edges[1:])):
                    self.log().critical('values of bin edges are not increasing: %s', str(edges))
                    raise RuntimeError('invalid bin edges specified')

    @property
    def variable(self):
        """
        Get name of variable represented by the histogram.

        :returns: variable name
        :rtype: string
        """
        return self._variable

    @variable.setter
    def variable(self, var):
        """
        Set name of variable represented by the histogram.

        :param str var: name of variable represented by the histogram.
        :raises RunTimeError: If a variable name already exists, it will not overwritten.
        """
        if hasattr(self, '_variable'):
            raise RuntimeError('histogram variable already set')
        self._variable = str(var)

    @property
    def datatype(self):
        """
        Get datatype of the variable represented by the histogram.

        :returns: data type
        :rtype: type
        """
        return self._datatype

    @datatype.setter
    def datatype(self, dt):
        """
        Set data type of the variable represented by the histogram.

        :param type dt: type of the variable represented by the histogram.
        :raises RunTimeError: If datatype has already been set, it will not overwritten.
        """
        if hasattr(self, '_datatype'):
            raise RuntimeError('datatype already set')
        self._datatype = dt

    @property
    def num_bins(self):
        """
        Return the number of bins in the ValueCounts object.

        :returns: number of bins
        :rtype: int
        """
        return self._val_counts.num_bins

    def get_bin_labels(self):
        """
        Return all bin labels

        :returns: array of all bin labels.
        :rtype: array
        """
        return [v[0] for v in self._val_counts.nononecounts.keys()]

    def get_uniform_bin_edges(self):
        """
        Return numpy style bin_edges array with uniform binning.

        :returns: array of all bin edges
        :rtype: array
        """
        if not self.bin_specs:
            return None
        bin_range = list(self.get_nonone_bin_range())
        return self.truncated_bin_edges(variable_range=bin_range)

    def get_nonone_bin_edges(self):
        """
        Return numpy style bin_edges array of the in bins the value_counts object.

        :returns: array of the bin edges
        :rtype: array
        """
        if not self.bin_specs:
            return None
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
        else:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0)
            edges = [
                offset +
                v[0] *
                width for v in self._val_counts.nononecounts.keys()]
            bin_edges = edges + [edges[-1] + width]
        return bin_edges

    def get_nonone_bin_centers(self):
        """
        Return the bin centers of the known bins in the value_counts object.

        :returns: array of the bin centers
        :rtype: array
        """
        if not self.bin_specs or len(self.bin_specs) == 0:
            return self.get_bin_labels()
        if 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            # NOTE: computation below also works with timestamps! Order is
            # important.
            bin_centers = []
            for i in range(len(bin_edges) - 1):
                bin_width = bin_edges[i + 1] - bin_edges[i]
                bin_width_half = bin_width / 2.
                bin_center = bin_edges[i] + bin_width_half
                bin_centers.append(bin_center)
        else:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0)
            bin_centers = [
                offset + (v[0] + 0.5) * width for v in self._val_counts.nononecounts.keys()]
        return bin_centers

    def get_bin_count(self, bin_label):
        """ Get bin count for specific bin, based on bin's label.

        :param bin_label: a specific key to find corresponding bin.
        :returns: bin counter value
        :rtype: int
        """
        return self._val_counts.nononecounts.get((bin_label,), 0)

    def get_nonone_bin_counts(self):
        """
        Return the bin counts of the known bins in the value_counts object.

        :returns: array of the bin counts
        :rtype: array
        """
        if not self.bin_specs or len(self.bin_specs) == 0:
            bin_counts = self._val_counts.nononecounts.values()
        elif 'bin_edges' in self.bin_specs:
            bin_edges = self.bin_specs['bin_edges']
            # NOTE: computation below also works with timestamps! Order is
            # important.
            bin_centers = []
            for i in range(len(bin_edges) - 1):
                bin_width = bin_edges[i + 1] - bin_edges[i]
                bin_width_half = bin_width / 2.
                bin_center = bin_edges[i] + bin_width_half
                bin_centers.append(bin_center)
            bin_counts = [self.get_hist_val(bc) for bc in bin_centers]
        else:
            bin_counts = self._val_counts.nononecounts.values()
        return bin_counts

    def get_bin_range(self):
        """
        Return the bin range of the known bins in the value_counts object.

        :returns: tuple of the bin range found
        :rtype: tuple
        """
        return self.get_nonone_bin_range()

    def get_nonone_bin_range(self):
        """
        Return the bin range of the known bins in the value_counts object.

        :returns: tuple of the bin range found
        :rtype: tuple
        """
        if not self.bin_specs:
            return None
        if 'bin_edges' in self.bin_specs:
            return self.bin_specs['bin_edges'][
                0], self.bin_specs['bin_edges'][-1]
        vals = [v[0] for v in self._val_counts.nononecounts.keys()]
        min_max = (vals[0], vals[-1])
        if self.bin_specs:
            width = self.bin_specs['bin_width']
            offset = self.bin_specs.get('bin_offset', 0.)
            return tuple(
                offset + m * width for m in (min_max[0], min_max[1] + 1))
        return min_max

    def get_hist_val(self, var_value):
        """ Get bin count for specific bin, based on the value that falls in that bin

        :param var_value: a specific value to find corresponding bin.
        :returns: bin counter value
        :rtype: int
        """
        try:
            bin_label = self.value_to_bin_label(var_value)
        except Exception as exc:
            self.log().error(
                'bin label for variable value "%s" not found (%s)',
                str(var_value),
                exc.message)
            return 0
        return self.get_bin_count(bin_label)

    def get_bin_vals(self, variable_range=[], combine_values=True):
        """ Creates lists of bin labels/edges and corresponding bin counts

        Bin values corresponding to a given variable range.

        :param list variable_range: variable range used for finding the right bins to get values from.
        :param bool combine_values: if bin_specs is not set, combine existing bin labels with variable range.
        :returns: two arrays of bin values and bin edges
        :rtype: array
        """
        # check type of input arguments
        variable_range = tuple(variable_range)
        combine_values = bool(combine_values)

        # create NumPy arrays of bin labels/edges
        if variable_range and not self.bin_specs:
            labs = bins = np.unique(np.append(self.get_bin_labels(), variable_range)) if combine_values else \
                np.array(variable_range)
        else:
            labs = np.array(self.get_bin_labels())
            bins = labs if not self.bin_specs else np.array(
                self.get_nonone_bin_edges())

        if variable_range and self.bin_specs:
            bins = self.truncated_bin_edges(
                variable_range=list(variable_range))
            # NOTE: computation below also works with timestamps! Order is
            # important.
            bin_centers = []
            for i in range(len(bins) - 1):
                bin_width = bins[i + 1] - bins[i]
                bin_width_half = bin_width / 2.
                bin_center = bins[i] + bin_width_half
                bin_centers.append(bin_center)
            labs = [self.value_to_bin_label(bc) for bc in bin_centers]

        return np.array([self.get_bin_count(v) for v in labs]), bins

    def remove_keys_of_inconsistent_type(self, prefered_key_type=None):
        """ Remove all keys that have inconsistent data type(s)

        :param tuple prefered_key_type: the prefered key type to keep. Can be a tuple, list, or single type. E.g. str or (int,str,float).
        If None provided, the most common key type found is kept.
        """
        n_keys_prev = len(self._val_counts._cnts)
        self._val_counts.remove_keys_of_inconsistent_type(prefered_key_type)
        n_keys_new = len(self._val_counts._cnts)

        if n_keys_new < n_keys_prev:
            self.log().info('Removed <%d> inconsistent keys out of <%d>, requiring <%s> data type.' %
                            (n_keys_prev - n_keys_new, n_keys_prev,
                             prefered_key_type if prefered_key_type is not None else 'most common'))

    # see
    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rv_continuous.html
    def simulate(self, size, *args):
        """
        Simulates data using self (Histogram instance) as pdf.

        :param int size: number of data points to generate
        :return numpy.array generated_data: the generated data
        :return eskapade.analysis.histogram.Histogram: Histogram of the generated data
        """

        h_norm = self.to_normalized()
        hist, bins = h_norm.get_bin_vals(*args)
        values = np.random.rand(size)

        # check if Histogram is categorical or numeric
        if not self.bin_specs:
            generated_data = np.random.choice(bins, p=hist, size=size)
            vc = pd.Series(generated_data).value_counts() / \
                float(len(generated_data))
            h_sim = Histogram((vc.values, vc.index.values), variable='x')
        else:
            # see
            # http://stackoverflow.com/questions/17821458/random-number-from-histogram
            bin_midpoints = bins[:-1] + np.diff(bins) / 2
            cdf = np.cumsum(hist)
            generated_data = np.searchsorted(cdf, values)
            random_from_cdf = bin_midpoints[generated_data]
            h_sim = Histogram(
                np.histogram(
                    random_from_cdf,
                    bins=bins),
                variable=self.variable)
        return generated_data, h_sim

    def surface(self):
        """
        Calculates the surface of the histogram.

        :return surface
        """
        if not self.bin_specs:
            raise NotImplementedError(
                'Surface for categorical histograms is not implemented.')
        hist, bin_edges = self.get_bin_vals()
        bin_widths = np.diff(bin_edges)
        return np.multiply(hist, bin_widths).sum()

    def copy(self, **kwargs):
        """ Give a copy of this histogram

        :param str variable: assign new variable name
        """
        new_var_name = str(kwargs.pop('variable', self.variable))
        return Histogram(counts=self.get_bin_vals(
            **kwargs), variable=new_var_name)

    def to_normalized(self, **kwargs):
        """ Give a normalized copy of this histogram

        :param str new_var_name: assign new variable name
        :param list variable_range: variable range used for finding the right bins to get values from.
        :param bool combine_values: if bin_specs is not set, combine existing bin labels with variable range.
        """
        # convert to normalized histogram
        new_var_name = str(kwargs.pop('variable', self.variable))
        bin_vals = self.get_bin_vals(**kwargs)
        values = np.float64(bin_vals[0]) / bin_vals[0].sum()
        # When values is a numpy array of 1 element np.float64() returns a 0-dimensional array. See
        # https://github.com/numpy/numpy/issues/3161. The following
        # if-statement is a workaround for this issue.
        if not values.shape:
            values = values.reshape((1,))
        return Histogram(counts=(values, bin_vals[1]), variable=new_var_name)

    @classmethod
    def combine_hists(cls, hists, labels=False,
                      rel_bin_width_tol=1e-6, **kwargs):
        """ Combine a set of histograms

        :param array hists: array of Histograms to add up.
        :param label labels: histograms to add up have labels? (else are numeric) Default is False.
        :param str variable: name of variable described by the summed-up histogram
        :param float rel_bin_width_tol: relative tolerance between numeric bin edges.
        :returns: summed up histogram
        :rtype: Histogram
        """

        # parse input arguments
        new_var_name = str(kwargs.pop('variable', 'x'))
        cls.log().debug('Combining histograms into one new histogram for "%s"', new_var_name)

        try:
            bin_vals = [h.get_bin_vals(**kwargs) for h in hists]
        except:
            cls.log().critical('unable to get bin values from specified histograms (%s)', str(hists))
            raise RuntimeError('invalid input histograms specified')
        if not bin_vals:
            raise RuntimeError('no input histograms specified')

        # check histogram bins
        ref_bins = bin_vals[0][1]
        if labels:
            if not all(np.array_equal(ref_bins, h[1]) for h in bin_vals):
                cls.log().critical('histograms with different binnings specified:%s',
                                   *('\n' + str(h[1]) for h in hists))
                raise RuntimeError(
                    'histograms with different binnings specified')
        else:
            ref_bin_width = hists[0].bin_specs['bin_width']
            atol = rel_bin_width_tol * ref_bin_width
            if not all(np.allclose(
                    ref_bins, h[1], rtol=0, atol=atol) for h in bin_vals):
                cls.log().critical('histograms with different binnings specified:%s',
                                   *('\n' + str(h[1]) for h in hists))
                raise RuntimeError(
                    'histograms with different binnings specified')

        # return histogram with sum of bin counts
        return cls(counts=(
            np.sum((h[0] for h in bin_vals), axis=0), ref_bins), variable=new_var_name)

    def _from_value_counts(self, counts):
        """ Constructor function of Histogram class from ValueCounts

        :param ValueCounts counts: construct Histogram from ValueCounts object counts
        """
        # initialize value counts from ValueCounts object
        if self.variable not in counts.key:
            self.log().critical('variable "%s" not in value counts with variables (%s)', self.variable,
                                ', '.join('"%s"' % v for v in counts.key))
            raise RuntimeError('specified variable and counts do not match')
        self._val_counts = counts.create_sub_counts((self.variable,))

    def _from_dict(self, counts):
        """ Constructor function of Histogram class from dictionary

        :param dict counts: construct Histogram from ValueCounts dict object
        """
        # initialize value counts from dictionary
        counts = dict((k if isinstance(k, tuple) else (k,), v)
                      for k, v in counts.items())
        if not all(len(k) == 1 for k in counts.keys()):
            self.log().critical(
                'specified counts dictionary contains keys with multiple variable values')
            raise AssertionError('invalid format for counts keys')
        _check_num_vals(iter(counts.values()))
        self._val_counts = ValueCounts(
            (self.variable,), (self.variable,), counts)

    def _from_numpy(self, counts, bin_edges):
        """ Constructor function of Histogram class from numpy histogram

        :param array counts: numpy histogram counts array
        :param array bin_edges: construct Histogram from numpy histogram bin_edges array
        """
        # initialize from NumPy-style histogram
        _check_num_vals(counts)
        if len(counts) == len(bin_edges) - 1:
            # interpret specified variable values as bin edges
            del self._bin_specs
            self.bin_specs = {'bin_edges': list(bin_edges)}
            bin_edges = list(range(len(counts)))
        elif len(counts) != len(bin_edges):
            # cannot interpret specified variable values as bin values
            self.log().critical('numbers of specified variable values (%d) and value counts (%d) do not match',
                                len(bin_edges), len(counts))
            raise AssertionError(
                'specified variable values and value counts do not match')
        self._val_counts = ValueCounts((self.variable,), (self.variable,),
                                       dict(((v,), c) for c, v in zip(counts, bin_edges)))
