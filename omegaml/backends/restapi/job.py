class GenericJobResource(object):
    def __init__(self, om, is_async=False):
        self.om = om
        self.is_async = is_async

    def is_eager(self):
        return getattr(self.om.runtime.celeryapp.conf, 'CELERY_ALWAYS_EAGER', False)

    def run(self, job_id, query, payload):
        """
        Args:
            job_id (str): the name of the model
            query (dict): the query parameters
            payload (dict): the json body

        Returns:
            dict(job: id, result: dict)
        """
        om = self.om
        promise = om.runtime.job(job_id).run()
        result = self.prepare_result_from_run(promise.get(), job_id=job_id) if not self.is_async else promise
        return result

    def metadata(self, job_id, query, payload):
        return self._get_job_detail(job_id)

    def prepare_result_from_run(self, result, job_id=None, **kwargs):
        return self._get_job_detail(job_id)

    def _get_job_detail(self, job_id):
        meta = self.om.jobs.metadata(job_id)
        data = {
            'job': meta.name,
            'job_results': meta.attributes.get('job_results', {}),
            'job_runs': meta.attributes.get('job_runs', []),
            'created': meta.created,
        }
        if 'source_job' in meta.attributes:
            data['source_job'] = meta.attributes['source_job']
        return data
