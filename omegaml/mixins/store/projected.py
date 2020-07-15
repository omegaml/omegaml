import re

import pandas as pd
import six


class ProjectedMixin(object):
    """
    A OmegaStore mixin to process column specifications in dataset name
    """
    colspec_pattern = re.compile(r"(?P<name>.*)\[(?P<colspec>.*)\].*$")

    def metadata(self, name, *args, **kwargs):
        if isinstance(name, six.string_types):
            name, colspec = self._extract_column_specs(name)
        return super(ProjectedMixin, self).metadata(name, *args, **kwargs)

    def get(self, name, *args, **kwargs):
        """
        Return a projected dataset given a name of form name[colspec]

        colspec can be any of

        * a comma separated list of columns, e.g. foo[a,b]
        * an open-ended slice, e.g. foo[a:] => all columns following a, inclusive
        * an closed slice, e.g. foo[a:b] => all columns between a,b, inclusive
        * a close-ended slice, e.g. foo[:b] => all columns up to b, inclusive
        * an empty slice, e.g. foo[:] => all columns
        * a list of columns to exclude, e.g. foo[^b] => all columns except b

        :param name: (str) the name of the dataset, optionally including a
           column specification
        :return: the dataset with projected columns
        """
        # split base name from specs, get metadata
        name, colspec = self._extract_column_specs(name)
        if colspec is None:
            # no column spec in name, avoid projection
            data = super(ProjectedMixin, self).get(name, *args, **kwargs)
        else:
            # column specs in name, get projected data
            data = self._get_data_from_projection(name, colspec, *args, **kwargs)
        return data

    def _extract_column_specs(self, name):
        colspec_pattern = self.colspec_pattern
        match = colspec_pattern.match(name)
        colspec = None
        if match is not None:
            name, colspec = match.groups()
        return name, colspec

    def _get_data_from_projection(self, name, colspec, *args, **kwargs):
        # see if we can get columns from metadata
        # if so we can specify the columns before getting the data
        meta = self.metadata(name)
        if 'columns' in meta.kind_meta:
            colmap = meta.kind_meta['columns']
            if isinstance(colmap, dict):
                all_columns = list(colmap.keys())[1]
            else:
                # colmap is list of tuples (colname, storedname)
                all_columns = list(zip(*colmap))[1]
            columns = columnset(colspec, all_columns)
            kwargs['columns'] = columns
            data = super(ProjectedMixin, self).get(name, *args, **kwargs)
        else:
            # we don't have columns in metadata, get the data first
            # only subset on dataframes
            data = super(ProjectedMixin, self).get(name, *args, **kwargs)
            if isinstance(data, pd.DataFrame):
                all_columns = data.columns
                name, columns = columnset(colspec, all_columns)
                data = data[columns]
        return data


def columnset(colspec, all_columns):
    """
    find the specified columns in data[colspec] in list of all columns

    colspec can be any of

    * a comma separated list of columns, e.g. foo[a,b]
    * an open-ended slice, e.g. foo[a:] => all columns following a, inclusive
    * an closed slice, e.g. foo[a:b] => all columns between a,b, inclusive
    * a close-ended slice, e.g. foo[:b] => all columns up to b, inclusive
    * an empty slice, e.g. foo[:] => all columns
    * a list of columns to exclude, e.g. foo[^b] => all columns except b
    """
    if colspec is not None:
        if ':' in colspec:
            from_col, to_col = colspec.split(':')
            from_i = (all_columns.index(from_col)
                      if from_col else 0)
            to_i = (all_columns.index(to_col)
                    if to_col else len(all_columns)) + 1
            columns = all_columns[from_i:to_i]
        elif colspec.startswith('^'):
            columns = [col for col in all_columns
                       if col not in colspec[1:].split(',')]
        else:
            columns = colspec.split(',')
    else:
        columns = all_columns
    return columns
