class GenericScriptResource(object):
    def __init__(self, om, is_async=False):
        self.om = om
        self.is_async = is_async

    def is_eager(self):
        return getattr(self.om.runtime.celeryapp.conf, 'CELERY_ALWAYS_EAGER', False)

    def run(self, script_id, query, payload):
        """
        Args:
            script_id (str): the name of the model
            query (dict): the query parameters
            payload (dict): the json body

        Returns:
            result
        """
        om = self.om
        payload = {} if payload is None else payload
        promise = om.runtime.script(script_id).run(__format='python', **query, **payload)
        result = self.prepare_result_from_run(promise.get(), script_id=script_id) if not self.is_async else promise
        return result

    def prepare_result_from_run(self, result, script_id=None, **kwargs):
        return result
