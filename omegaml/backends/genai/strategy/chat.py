from uuid import uuid4

import pandas as pd


class ChatMixin:
    def chat(self, prompt, conversation_id=None, raw=False, stream=False, use_tools=True, **kwargs):
        """chat completions

        This is the same as ConversationModel.complete() however ensures a tracking provider and a data_store
        have been made active in order to store and retrieve previous messages.

        Args:
            prompt (str|list|dict): the prompt to use, see Text.complete() for details
            conversation_id (str): the conversation id, used to retrieve previous messages from the
              tracking provider, defaults to uuid4().hex for new conversations
            raw (bool): optional, defaults to False. If True returns messages in the original format of the
               provider API. If False returns just the latest response in a simplified format.
            stream (bool): optional, defaults to False. If True a generator is returned to consume response messages
            use_tools (bool): optional, defaults to True. If True, and tools have been specified for the model, the
               model is asked to choose a tool for execution, and any chosen tool will be executed by ConversationModel
               as part of the completion. If False, no tools will be provided to the model.
            **kwargs: optional, passed to ConversationModel.complete()

        Returns:
           response (dict|iterator): if stream==False, returns a dict of all model responses, if stream==True
              returns an iterator of streamed responses.
        """
        responses = self._do_chat(prompt, conversation_id=conversation_id, stream=stream, use_tools=use_tools, **kwargs)

        def response_parser(r):
            (conversation_id, response, prompt_response, response_message, raw_response) = r
            return conversation_id, (response if raw else response_message)

        response_gen = (response_parser(response) for response in responses if response)
        return response_gen if stream else [response for response in response_gen][-1]

    def _do_chat(
            self, prompt, messages=None, conversation_id=None, data=None, use_tools=False, raw=False, stream=False,
            **kwargs
    ):
        assert self.data_store, "chat requires a data_store, specify data_store=om.datasets"
        assert self.tracking, "chat requires a tracking instance, use with om.runtime.experiment(): ... "
        conversation_id = conversation_id or uuid4().hex
        # if the client sends in messages, don't recall past conversations (they are already in messages)
        messages = messages or self.conversation(conversation_id, raw=True)
        system_message_missing = not any(m.get('role') in ('system', 'developer') for m in messages)
        empty = lambda d: d.empty if isinstance(d, pd.DataFrame) else not d
        if empty(messages) or system_message_missing:
            # no message history, insert the system message to start off the conversation)
            messages = [self._system_message(self.prompt, conversation_id=conversation_id)] + (
                messages if messages else []
            )
            self._log_events('conversation', conversation_id, messages)
        responses = self._do_complete(
            prompt,
            messages=messages,
            conversation_id=conversation_id,
            data=data,
            use_tools=use_tools,
            raw=raw,
            stream=stream,
            **kwargs,
        )
        for response in responses:
            response, prompt_message, response_message, raw_response = response
            yield (conversation_id, response, prompt_message, response_message, raw_response)
