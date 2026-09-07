from pprint import pformat

import pandas as pd

from omegaml.util import ensure_dict, ensure_list


class TracingMixin:
    def trace(self, fn=None, methods=None):
        """trace pipeline calls

        Args:
            fn (callable): a callable, accepting the same arguments as a pipeline function
            methods (list): optional, specify the pipeline methods to trace, e.g. prepare, complete,
               toolprepare, toolcall, toolresult, process

        Returns:
            self
        """
        methods = methods or []

        def tracefn(*args, method=None, **kwargs):
            if not methods or method in methods:
                print(f"tracing method={method}", pformat(kwargs))

        self.trace_fn = fn if callable(fn) else tracefn
        return self

    def conversation(self, conversation_id=None, raw=False, **filter):
        """Retrieve conversation messages

        Args:
            conversation_id (str): the conversation id to retrieve messages for
            raw (bool): if True, return raw messages as dicts, otherwise return a DataFrame
            filter (dict): additional filters to apply to the conversation messages

        Returns:
            pd.DataFrame or list[dict]: the conversation messages, either as a DataFrame or a list of dicts
        """
        assert self.data_store, "this model does not track conversations, specify .get(...., data_store=om.datasets)"
        assert self.tracking, "this model does not track conversations, use with om.runtime.experiment(): ... "
        filter.setdefault('run', '*')
        filter.setdefault('key', conversation_id)
        messages = self.tracking.data(event='conversation', **filter)
        if messages is not None and 'value' in messages.columns:
            messages = pd.concat([messages.reset_index(), pd.json_normalize(messages['value'])], axis=1)
            # FIXME fillna('') is deprecated for numeric columns (handle in serialization?)
            messages.fillna('', inplace=True)
            columns = list(set(messages.columns) & {'key', 'role', 'content', 'finish_reason', 'dt'})
            return messages[columns] if not raw else list(messages['value'].to_dict().values())
        return pd.DataFrame() if not raw else []

    def pipeline(self, *args, **kwargs):
        self.trace_fn(*args, **kwargs) if callable(self.trace_fn) else None
        return self.pipeline_fn(*args, **kwargs) or False

    def _log_events(self, event, conversation_id, data):
        if self.tracking:
            self.tracking.log_events(event, conversation_id, ensure_list(data))
            self.tracking.flush()

    def _track_usage(self, response, conversation_id):
        data = ensure_dict(response)
        if self.tracking:
            for metric, value in data.get('usage', {}).items():
                self.tracking.log_event('usage', metric, value, conversation_id=conversation_id)
