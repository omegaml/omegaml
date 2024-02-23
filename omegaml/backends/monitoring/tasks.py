from celery import shared_task

from omegaml.celery_util import OmegamlTask

code_block = """
# configure
import omegaml as om
# -- the name of the experiment
experiment = '{experiment}'
# -- the name of the model
name = '{meta.name}'
# -- the name of the monitoring provider
provider = '{provider}'
# -- the alert rules
alerts = {alerts}
# snapshot recent state and capture drift 
with om.runtime.model(name).experiment(experiment) as exp:
    mon = exp.as_monitor(name, store=om.models, provider=provider)
    # TODO run=-1, or since=dt for last run? in production we have many runs since the last one
    mon.snapshot(run='*') 
    mon.capture(alerts=alerts)
"""


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
    for meta in om.models.list(raw=True):
        monitors = meta.attributes.get('tracking', {}).get('monitors', [])
        for mon in monitors:
            experiment = mon['experiment']
            provider = mon['provider']
            job = mon.get('job') or f'monitors/{experiment}/{meta.name}'
            schedule = mon.get('schedule', 'daily')
            alerts = mon.get('alerts', [])
            if not om.jobs.list(job):
                # if job does not exist yet create it
                code = code_block.format(**locals())
                om.jobs.create(code, job)
                om.jobs.schedule(job, schedule=schedule)
                mon['job'] = job
                mon['schedule'] = schedule
                meta.save()
