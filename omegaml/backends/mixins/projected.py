import re


class ProjectedMixin(object):

    """
    A OmegaStore mixin to process column specifications in dataset name
    """
    colspec_pattern = re.compile(r"(?P<name>.*)\[(?P<colspec>.*)\]$")

    def get(self, name, *args, **kwargs):
        """
        Return a projected dataset given a name of form name[colspec]

        A column specification is a comma separated list of column names in 
        the dataset, e.g. datasets.get('foo[bar]'). This is the same as
        calling datasets.get('foo', columns=['bar']). 

        :param name: (str) the name of the dataset, optionally including a
           column specification
        :return: the dataset with projected columns 
        """
        match = self.colspec_pattern.match(name)
        if match is not None:
            name, colspec = match.groups()
            columns = colspec.split(',')
            kwargs['columns'] = columns
        return super(ProjectedMixin, self).get(name, *args, **kwargs)
