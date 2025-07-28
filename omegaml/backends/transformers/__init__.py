from zipfile import ZipFile, ZIP_DEFLATED

import glob
import os
import tempfile
from shutil import rmtree

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.transformers.serialize import TransformersPipelineSerializer


class TransformerModelBackend(BaseModelBackend):
    KIND = 'hf.pipeline'

    @classmethod
    def supports(self, obj, name, **kwargs):
        from transformers import Pipeline
        return isinstance(obj, Pipeline)

    def put_model(self, obj, name, attributes=None, _kind_version=None, **kwargs):
        meta = super().put_model(obj, name, attributes=attributes, _kind_version=_kind_version, **kwargs)
        meta.kind_meta['task'] = obj.task
        return meta.save()

    def _package_model(self, model, key, tmpfn, serving_input_fn=None,
                       strip_default_attrs=None, **kwargs):
        export_dir_base = self._make_savedmodel(model)
        zipfname = self._package_savedmodel(export_dir_base, key)
        rmtree(export_dir_base)
        return zipfname

    def _make_savedmodel(self, obj):
        # adapted from https://www.tensorflow.org/guide/saved_model#perform_the_export
        export_dir_base = tempfile.mkdtemp()
        serializer = TransformersPipelineSerializer()
        serializer.save(obj, export_dir_base)
        return export_dir_base

    def _extract_model(self, infile, key, tmpfn, meta=None, **kwargs):
        with open(tmpfn, 'wb') as pkgfn:
            pkgfn.write(infile.read())
        task = meta.kind_meta['task']
        model = self._extract_savedmodel(tmpfn, task)
        return model

    def _package_savedmodel(self, export_base_dir, filename):
        fname = os.path.basename(filename)
        zipfname = os.path.join(self.model_store.tmppath, fname)
        # check if we have an intermediate directory (timestamp)
        # as in export_base_dir/<timestamp>, if so, use this as the base directory
        # see https://www.tensorflow.org/guide/saved_model#perform_the_export
        # we need this check because not all SavedModel exports create a timestamp
        # directory. e.g. keras.save_keras_model() does not, while Estimator.export_saved_model does
        files = glob.glob(os.path.join(export_base_dir, '*'))
        if len(files) == 1:
            export_base_dir = files[0]
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for part in glob.glob(os.path.join(export_base_dir, '**'), recursive=True):
                zipf.write(part, os.path.relpath(part, export_base_dir))
        return zipfname

    def _extract_savedmodel(self, packagefname, task):
        lpath = tempfile.mkdtemp()
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        serializer = TransformersPipelineSerializer()
        model = serializer.load(lpath)
        rmtree(lpath)
        return model

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        predict using data stored in Xname

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the result data object or None
        :param pure_python: if True return a python object. If False return
            a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the predicted outcome
        """
        model = self.model_store.get(modelname)
        data = self._resolve_input_data('predict', Xname, 'X', **kwargs)
        result = model.predict(data[-1])
        return self._prepare_result('predict', result, rName=rName,
                                    pure_python=pure_python, **kwargs)
