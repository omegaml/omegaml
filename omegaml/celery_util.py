import six
from celery import Task


class OmegamlTask(Task):
    abstract = True

    def __init__(self, *args, **kwargs):
        super(OmegamlTask, self).__init__(*args, **kwargs)
        self._om = None

    @property
    def om(self):
        if self._om is None:
            from omegaml import get_omega_for_task
            self._om = get_omega_for_task(self)
        return self._om

    def get_delegate(self, name, kind='models'):
        get_delegate_provider = getattr(self.om, kind)
        return get_delegate_provider.get_backend(name, data_store=self.om.datasets)

    @property
    def delegate_args(self):
        return self.request.args

    @property
    def delegate_kwargs(self):
        return {k: v for k, v in six.iteritems(self.request.kwargs) if not k.startswith('__')}


def get_dataset_representations(items):
    """
    returns dict with x and y datasets
    """
    results = {}
    results['Xname'] = items.get('Xname')
    results['Yname'] = items.get('Yname')
    return results
