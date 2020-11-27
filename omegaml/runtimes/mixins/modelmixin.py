from __future__ import absolute_import

import logging
import six
from uuid import uuid4

from omegaml.util import is_dataframe, is_ndarray

logger = logging.getLogger(__file__)


class ModelMixin(object):
    def fit(self, Xname, Yname=None, **kwargs):
        """
        fit the model

        Calls :code:`.fit(X, Y, **kwargs)`. If instead of dataset names actual data
        is given, the data is stored using _fitX/fitY prefixes and a unique
        name.

        After fitting, a new model version is stored with its attributes
        fitX and fitY pointing to the datasets, as well as the sklearn
        version used.

        :param Xname: name of X dataset or data
        :param Yname: name of Y dataset or data
        :return: the model (self) or the string representation (python clients)
        """
        omega_fit = self.task('omegaml.tasks.omega_fit')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return omega_fit.delay(self.modelname, Xname, Yname, **kwargs)

    def partial_fit(self, Xname, Yname=None, **kwargs):
        """
        update the model

        Calls :code:`.partial_fit(X, Y, **kwargs)`. If instead of dataset names actual
        data  is given, the data is stored using _fitX/fitY prefixes and
        a unique name.

        After fitting, a new model version is stored with its attributes
        fitX and fitY pointing to the datasets, as well as the sklearn
        version used.

        :param Xname: name of X dataset or data
        :param Yname: name of Y dataset or data
        :return: the model (self) or the string representation (python clients)
        """
        omega_fit = self.task('omegaml.tasks.omega_partial_fit')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return omega_fit.delay(self.modelname, Xname, Yname, **kwargs)

    def transform(self, Xname, rName=None, **kwargs):
        """
        transform X

        Calls :code:`.transform(X, **kwargs)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .transform, or the metadata of the rName
            dataset if rName was given
        """
        omega_transform = self.task('omegaml.tasks.omega_transform')
        Xname = self._ensure_data_is_stored(Xname)
        return omega_transform.delay(self.modelname, Xname,
                                     rName=rName, **kwargs)

    def fit_transform(self, Xname, Yname=None, rName=None, **kwargs):
        """
        fit & transform X

        Calls :code:`.fit_transform(X, Y, **kwargs)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param Yname: name of the Y dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .fit_transform, or the metadata of the rName
           dataset if rName was given
        """

        omega_fit_transform = self.task(
            'omegaml.tasks.omega_fit_transform')
        Xname = self._ensure_data_is_stored(Xname)
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname)
        return omega_fit_transform.delay(self.modelname, Xname, Yname,
                                         rName=rName, transform=True, **kwargs)

    def predict(self, Xpath_or_data, rName=None, **kwargs):
        """
        predict

        Calls :code:`.predict(X)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .predict, or the metadata of the rName
            dataset if rName was given
        """
        omega_predict = self.task('omegaml.tasks.omega_predict')
        Xname = self._ensure_data_is_stored(Xpath_or_data)
        return omega_predict.delay(self.modelname, Xname, rName=rName, **kwargs)

    def predict_proba(self, Xpath_or_data, rName=None, **kwargs):
        """
        predict probabilities

        Calls :code:`.predict_proba(X)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .predict_proba, or the metadata of the rName
           dataset if rName was given
        """
        omega_predict_proba = self.task(
            'omegaml.tasks.omega_predict_proba')
        Xname = self._ensure_data_is_stored(Xpath_or_data)
        return omega_predict_proba.delay(self.modelname, Xname, rName=rName, **kwargs)

    def score(self, Xname, Yname=None, rName=None, **kwargs):
        """
        calculate score

        Calls :code:`.score(X, y, **kwargs)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param yName: name of the y dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .score, or the metadata of the rName
           dataset if rName was given
        """
        omega_score = self.task('omegaml.tasks.omega_score')
        Xname = self._ensure_data_is_stored(Xname)
        yName = self._ensure_data_is_stored(Yname)
        return omega_score.delay(self.modelname, Xname, yName, rName=rName, **kwargs)

    def decision_function(self, Xname, rName=None, **kwargs):
        """
        calculate score

        Calls :code:`.decision_function(X, y, **kwargs)`. If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .score, or the metadata of the rName
           dataset if rName was given
        """
        omega_decision_function = self.task('omegaml.tasks.omega_decision_function')
        Xname = self._ensure_data_is_stored(Xname)
        return omega_decision_function.delay(self.modelname, Xname, rName=rName, **kwargs)

    def reduce(self, rName=None, **kwargs):
        omega_reduce = self.task('omegaml.tasks.omega_reduce')
        return omega_reduce.delay(modelName=self.modelname, rName=rName, **kwargs)

    def _ensure_data_is_stored(self, name_or_data, prefix='_temp'):
        if is_dataframe(name_or_data):
            name = '%s_%s' % (prefix, uuid4().hex)
            self.runtime.omega.datasets.put(name_or_data, name)
        elif is_ndarray(name_or_data):
            name = '%s_%s' % (prefix, uuid4().hex)
            self.runtime.omega.datasets.put(name_or_data, name)
        elif isinstance(name_or_data, (list, tuple, dict)):
            name = '%s_%s' % (prefix, uuid4().hex)
            self.runtime.omega.datasets.put(name_or_data, name)
        elif isinstance(name_or_data, six.string_types):
            name = name_or_data
        else:
            raise TypeError(
                'invalid type for Xpath_or_data', type(name_or_data))
        return name
