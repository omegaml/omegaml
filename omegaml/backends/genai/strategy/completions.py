import logging
from itertools import chain
from uuid import uuid4

from omegaml.util import dict_merge, safeformat

logger = logging.getLogger(__name__)


class CompletionsMixin:
    def complete(
            self,
            prompt,
            messages=None,
            conversation_id=None,
            raw=False,
            data=None,
            stream=False,
            use_tools=True,
            chat=False,
            trace=None,
            agentic=False,
            tools=None,
            **kwargs,
    ):
        """complete a prompt

        Will call the provider's chat.completion endpoint. Can be called in two modes:
        1) completion without conversation tracking (no conversation id, chat=False),
        2) chat completion with conversation tracking (chat=True, or conversation id).

        Args:
            prompt (str|dict|list): the input prompt to pass to the model. A string will
               be converted to an input message; a dict as appended as the last message to all
               messages, a list is assumed to be a list of fully formed messages as required by the
               openai /chat/completions endpoint
            messages (list[dict]): optional, a list of previous messages. If a conversation_id is
               specified and if tracking is enabled, the messages are retrieved from the tracking provider
            conversation_id (str): optional, a unique id for the conversation, defaults to uuid4().hex
            raw (bool): optional, defaults to False. If True returns messages in the original format of the
               provider API. If False returns just the latest response in a simplified format.
            data (dict): optional, if specified will be used to replace {placeholders} in the model's template,
               using template.format_map(data)
            stream (bool): optional, defaults to False. If True a generator is returned to consume response messages
            chat (bool): optional, defaults to False. If True will use ConversationModel.chat() to complete the call. requires a tracking
               provider and a data_store to track all 'conversation' events (input + output messages)
            use_tools (bool): optional, defaults to True. If True, and tools have been specified for the model, the
               model is asked to choose a tool for execution, and any chosen tool will be executed by ConversationModel
               as part of the completion. If False, no tools will be provided to the model.
            agentic (bool): optional, defaults to False. If True, will recursively resolve tool calls until no further
                tools are called by the model. This implies tools=True if tools are present. Tool calls are not
                streamed. This can also be set permanently by saving a model with models.put(..., strategy={
                'agentic': True})
            **kwargs:

        Returns:
            response (dict|iterator): if stream==False, returns a dict of all model responses, if stream==True
              returns an iterator of streamed responses.

        .. versionchanged:: NEXT
            ConversationModel.complete(..., agentic=True) will recursively resolve calls until no further tools are
            called by the model. This implies tools=True if tools are present. Tool calls are not streamed. This
            can also be set permanently by saving a model with models.put(..., strategy={'agentic': True})
        """
        self.trace(trace) if locals().get('trace') else None

        agentic = agentic or self.strategy.get('agentic', False)
        if agentic:
            conversation_id = conversation_id or uuid4().hex
            use_tools = True
        if tools:
            self.tools.extend(tools)

        def parse_completion_response(r):
            response, _, response_message, raw_response = r
            return response_message if not raw else response

        def parse_chat_response(r):
            conversation_id, response, _, response_message, raw_response = r
            return response_message if not raw else response

        def generate_response_stream_once(prompt, messages, use_tools):
            if not chat and conversation_id is None:
                responses = self._do_complete(
                    prompt, messages=messages, data=data, stream=stream, use_tools=use_tools, raw=raw, **kwargs
                )
                response_parser = parse_completion_response
            else:
                # chat or conversation id provided
                responses = self._do_chat(
                    prompt,
                    messages=messages,
                    conversation_id=conversation_id,
                    data=data,
                    stream=stream,
                    use_tools=use_tools,
                    raw=raw,
                    **kwargs,
                )
                response_parser = parse_chat_response
            # return response(s)
            # -- parse, then check if parsed is a valid object (avoid passing on a generator)
            parsed_gen = (response_parser(response) for response in responses)
            response_gen = (parsed for parsed in parsed_gen if isinstance(parsed, (list, dict, tuple)))
            return response_gen

        def generate_response_loop(prompt, messages, use_tools):
            turn_prompt = prompt
            intermediate_results = None
            while True:
                response = None
                tool_calls = None
                # the stream may contain multiple partial toolcall messages
                # -- first, generate the full stream until it stops
                # -- then, check for tool calls across the consolidate stream
                for response in generate_response_stream_once(turn_prompt, messages, use_tools=True):
                    try:
                        if not raw and intermediate_results:
                            # FIXME move to conversation state
                            response.setdefault('intermediate_results', []).append(intermediate_results)
                            intermediate_results = None
                        yield response
                        tool_calls = self._has_tool_calls(response)
                    except Exception as e:
                        logger.warning(f'could not process response due to {e} in {conversation_id=}', exc_info=True)
                if response and tool_calls and (agentic or use_tools):
                    intermediate_results, tool_prompts = self._handle_toolcalls(response, tool_calls, conversation_id)
                    turn_prompt = tool_prompts
                    continue
                else:
                    break

        response_gen = generate_response_loop(prompt, messages, use_tools)
        return response_gen if stream else [response for response in response_gen][-1]

    def _do_complete(
            self, prompt, messages=None, conversation_id=None, data=None, stream=False, use_tools=False, raw=False,
            **kwargs
    ):
        conversation_id = conversation_id or uuid4().hex
        messages = messages or []
        kwargs.update(self.strategy.get('complete', {}))
        kwargs.update(stream=stream)
        # prepare tools
        if self.tools:
            kwargs.update(tools=self.tools_specs(self.tools), tool_choice='auto')
        # prepare template
        _template = self._prepare_template(self.template, data=data)
        template = (
                self.pipeline(
                    method='template',
                    prompt_message=prompt,
                    messages=messages,
                    template=self.template,
                    conversation_id=conversation_id,
                    **kwargs,
                )
                or _template
        )
        if prompt and isinstance(prompt, str):
            # support direct text input
            prompt_message = {"role": "user", "content": prompt, "conversation_id": conversation_id}
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            messages += [self._augment_message(prompt_message, documents=self.documents, template=template)]
        elif isinstance(prompt, dict):
            # support structured input
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            messages += [self._augment_message(prompt, documents=self.documents, template=template)]
            prompt_message = messages[-1]
        elif isinstance(prompt, list):
            # support structured input, as messages
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            # augment last message only
            messages += prompt[:-1] if len(prompt) > 1 else []
            messages += [self._augment_message(prompt[-1], documents=self.documents, template=template)]
            prompt_message = messages[-1]
        else:
            # raw input, assume messages contains the user prompt
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            # augment last message only
            messages[-1] = self._augment_message(messages[-1], documents=self.documents, template=template)
            prompt_message = messages[-1]
        # prepare messages
        _default_messages = messages
        messages = (
                self.pipeline(
                    method='prepare',
                    prompt_message=prompt_message,
                    messages=messages,
                    template=template,
                    conversation_id=conversation_id,
                    **kwargs,
                )
                or _default_messages
        )
        # produce a response by calling the pipeline or the model
        response = self.pipeline(
            method='complete',
            prompt_message=prompt_message,
            messages=messages,
            template=template,
            conversation_id=conversation_id,
            **kwargs,
        )
        # finally call the model provider, if needed
        self._log_events('conversation', conversation_id, prompt_message)
        response = response or self.provider.complete(messages=messages, model=self.model, **kwargs)

        def capture_tool_calls(
                response, prompt_message, response_message, use_tools=False, as_delta=False, chunks=None
        ):
            """capture toolcalls across stream messages to consolidate into a single, fully formatted toolcall

            Combines previously streamed 'tool_calls' messages into a properly formatted, combined tool call. This
            is because tool calls can be sent as partial specifications across several streamed messages

            See Also:
                - https://developers.openai.com/api/docs/guides/function-calling#streaming
                - https://www.perplexity.ai/search/718b5969-fce4-4ad6-bd4b-e1fe66de9d8e
            """
            tool_message = self._get_response_message(response_message)
            should_call = response['choices'][0].get('finish_reason') == 'tool_calls'
            if should_call and self.tools:
                if chunks:
                    # consolidate previous chunks, if any
                    # -- in streaming mode, tool_calls can be sent in multiple chunks
                    # -- merge partial tool_calls by index
                    tool_calls_map = {}
                    chunked_msgs = (self._get_response_message(c) for c in chunks)
                    chunked_calls = (c.get('tool_calls') for c in chunked_msgs if 'tool_calls' in c)
                    partial_calls = chain.from_iterable(c for c in chunked_calls)
                    for partial_call in partial_calls:
                        idx = partial_call.get('index', 0)
                        tool_calls_map.setdefault(idx, tool_message.get('tool_calls') or {})
                        dict_merge(tool_calls_map[idx], partial_call)
                    # -- finalize tool call message
                    tool_calls = list(sorted(tool_calls_map.values(), key=lambda v: v.get('index')))
                else:
                    tool_calls = tool_message.get('tool_calls')
                if use_tools and tool_calls:
                    tool_calls = (
                            self.pipeline(
                                method='toolprepare',
                                prompt_message=prompt_message,
                                response_message=response_message,
                                messages=messages,
                                tool_calls=tool_calls,
                                template=template,
                                conversation_id=conversation_id,
                                **kwargs,
                            )
                            or tool_calls
                    )
                    response_message['tool_calls'] = tool_calls
            return response, prompt_message, response_message

        def resolve_response(response, prompt_message, use_tools=False):
            raw_response = response.to_dict() if hasattr(response, 'to_dict') else response
            if len(raw_response['choices']) == 0:
                # this should not happen per the protocol - if it does, simulate an empty delta
                raw_response['choices'].append({'message': {'content': None}})
            if 'error' in response:
                return (
                    response,
                    prompt_message,
                    {
                        "role": "system",
                        "content": response['error'].get('message', str(response['error'])),
                        "conversation_id": conversation_id,
                        "error": response['error'],
                    },
                    raw_response,
                )
            response_message = response['choices'][0]['message']
            response_message.setdefault('conversation_id', conversation_id)
            response, prompt_message, response_message = capture_tool_calls(
                response, prompt_message, response_message, use_tools=use_tools
            )
            response_message = (
                    self.pipeline(
                        method='process',
                        response_message=response_message,
                        prompt_message=prompt_message,
                        messages=messages,
                        template=template,
                        conversation_id=conversation_id,
                        **kwargs,
                    )
                    or response_message
            )
            return response, prompt_message, response_message, raw_response

        def resolve_chunk(response, chunk, chunks, prompt_message, consolidated_response, use_tools=False):
            """resolve a single chunk of a streamed response

            Args:
                response (OpenAIResponse): the full response object
                chunk (OpenAIResponseChunk): the current chunk of the response
                chunks (list): list of all chunks received so far
                prompt_message (dict): the prompt message used for this request
                consolidated_response (dict): the consolidated response so far
                use_tools (bool): whether to use tools in this response

            Returns:
                tuple: (response, prompt_message, response_message, raw_response)

                where:
                    response: the full response object
                    prompt_message: the prompt message used for this request
                    response_message: the response message as a dictionary (choices[0].delta)
                    raw_response: the raw response chunk as a dictionary

            """
            raw_response = chunk.to_dict() if hasattr(chunk, 'to_dict') else chunk
            # consolidate content
            content = ''.join(
                c['choices'][0]['delta'].get('content') or ''  # fmt:asis
                for c in chunks
            ) + str(chunk['choices'][0]['delta'].get('content') or '')
            reasoning = ''.join(
                c['choices'][0]['delta'].get('reasoning') or ''  # fmt:asis
                for c in chunks
            ) + str(chunk['choices'][0]['delta'].get('reasoning') or '')
            if chunk['choices']:
                if raw:
                    response_message = chunk['choices'][0]['delta']
                else:
                    response_message = {
                        "role": chunk['choices'][0]['delta'].get('role'),
                        "delta": chunk['choices'][0]['delta'].get('content'),
                        'reasoning': reasoning,
                        "content": content,
                        "conversation_id": conversation_id,
                        "tool_calls": chunk['choices'][0]['delta'].get('tool_calls'),
                        "finish_reason": chunk['choices'][0].get('finish_reason'),
                    }
                    # response_message.update(consolidated)
                response_message.setdefault('conversation_id', conversation_id)
                response, prompt_message, response_message = capture_tool_calls(
                    chunk, prompt_message, response_message, use_tools=use_tools, as_delta=True, chunks=chunks
                )
                response_message = (
                        self.pipeline(
                            method='process',
                            response_message=response_message,
                            prompt_message=prompt_message,
                            messages=messages,
                            template=template,
                            conversation_id=conversation_id,
                            **kwargs,
                        )
                        or response_message
                )
            else:
                content = ''
            # consolidate response
            consolidated_response.update({'content': content, 'reasoning': reasoning})
            consolidated_response.update(response_message)
            chunks.append(raw_response)
            return response, prompt_message, response_message, raw_response

        if stream:
            chunks = []
            consolidated_response = {}
            # -- wrap generator in try/finally to ensure we capture consolidated response even if client aborts
            try:
                for chunk in response:
                    try:
                        self._track_usage(chunk, conversation_id)
                        resolved = resolve_chunk(
                            response, chunk, chunks, prompt_message, consolidated_response, use_tools=use_tools
                        )
                    except Exception as e:
                        logger.warning(f"could not process chunk {chunk.get('id')} due to {e}", exc_info=True)
                        self._log_events(
                            'error', conversation_id, f'could not process stream chunk due to {e} {chunk=}'
                        )
                        response_message = {'error': f'could not process stream chunk for {conversation_id=}'}
                        consolidated_response.update(response_message)
                        yield response, prompt_message, response_message, response_message
                    else:
                        yield resolved
            finally:
                # log consolidated response only
                if consolidated_response:
                    self._log_events('conversation', conversation_id, consolidated_response)
        else:
            try:
                self._track_usage(response, conversation_id)
                yield resolve_response(response, prompt_message, use_tools=use_tools)
            except Exception as e:
                logger.warning(f"Could not process chunk {response.get('id')} due to {e}")
                self._log_events('error', conversation_id, [response])
            finally:
                self._log_events('conversation', conversation_id, self._get_response_message(response))

    def _parsed_completion(self, response):
        return response['choices'][0]['message'].get('content')

    def _prepare_template(self, template, data=None):
        _template = (template or '').format_map(safeformat(data or {}))
        return template

    def _get_response_message(self, response):
        # return the current response message or chunk
        if 'role' in response:
            # that's already a message
            return response
        if 'delta' in response['choices'][0]:
            message = response['choices'][0]['delta']
        else:
            message = response['choices'][0]['message']
        return message

    def _has_tool_calls(self, response):
        message = self._get_response_message(response)
        return message.get('tool_calls') or []
