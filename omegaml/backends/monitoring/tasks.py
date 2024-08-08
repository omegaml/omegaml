from celery import shared_task

from omegaml.celery_util import OmegamlTask


@shared_task(base=OmegamlTask, bind=True)
def ensure_monitors(self, **kwargs):
    """
    Ensure monitors are created for all models that have tracking.monitors set

    This creates a job for each monitor definition in the model's metadata. The job
    will run daily and capture the model's state and drift. Alerts are sent to the
    recipients specified in the monitor definition. If a job already exists it is not
    created again.

    The name of the job is derived from the model's name and the experiment's name in
    the form 'monitors/{experiment}/{modelname}'. The schedule is set to 'daily'
    unless specified in the monitor definition in

    Args:
        self:
        **kwargs:

    Returns:
        None
    """
    om = self.om
    for obj in om.models.list():
        if obj.startswith('experiments'):
            continue
        with om.runtime.model(obj).experiment() as exp:
            exp._create_monitor_job(obj, om.models, om.jobs)
