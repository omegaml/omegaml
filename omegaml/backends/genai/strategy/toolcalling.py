import json


class ToolCallingMixin:
    def tools_specs(self, tools):
        return [self._get_function_spec(tool) for tool in tools]

    def _get_function_spec(self, func):
        """
        Generates an OpenAI SDK function dictionary from an annotated function.

        Args:
            func (callable): The annotated function to be converted.

        Returns:
            dict: The OpenAI SDK function dictionary.

        References:
            - https://platform.openai.com/docs/api-reference/debugging-requests
        """
        if isinstance(func, dict):
            return func
        import inspect

        sig = inspect.signature(func)
        params = {}
        TYPES = {str: 'string', int: 'integer', float: 'float', list: 'list'}
        for param in sig.parameters.values():
            param_type = (
                TYPES.get(param.annotation) or 'string' if param.annotation != inspect.Parameter.empty else None
            )
            param_default = param.default if param.default != inspect.Parameter.empty else None
            param_type = param_type or TYPES.get(type(param_default))
            param_dict = {
                "name": param.name,
                "type": param_type,
                "description": f'represents {param.name}',
                "default": param_default,
            }
            params[param.name] = param_dict

        return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else None

        function_dict = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": inspect.getdoc(func) or 'A function to return a response',
                "parameters": {"type": "object", "properties": {k: v for k, v in params.items()}},
                "return_type": return_type,
            },
        }

        return function_dict

    def _handle_toolcalls(self, response, tool_calls, conversation_id):
        results, tool_prompts = self._call_tools(tool_calls, conversation_id)
        tool_prompts = (
                self.pipeline(
                    method='toolcall',
                    prompt_message=None,  # FIXME
                    response_message=response,
                    messages=None,  # FIXME
                    tool_prompts=tool_prompts,
                    tool_results=results,
                    template=None,  # FIXME
                    conversation_id=conversation_id,
                )
                or tool_prompts
        )
        return results, tool_prompts

    def _call_tools(self, tool_calls, conversation_id):
        # process tool calls
        tool_results = []
        tool_prompts = []
        for tool_call in tool_calls:
            tool_specs_callables = zip(self.tools_specs(self.tools), self.tools)
            tool_name = tool_call['function'].get('name')
            tool_id = tool_call.get('id')
            tool_args = tool_call['function'].get('arguments', '')
            matched_tool = [(ts, tf) for ts, tf in tool_specs_callables if tf.__name__ == tool_name]
            if matched_tool:
                tool, tool_func = matched_tool[0]
                try:
                    tool_args = json.loads(tool_args)
                    # parse e.g. '{"args": ["is 10 correct?"], "kwargs": {}}'
                    if isinstance(tool_args, dict) and "args" in tool_args and "kwargs" in tool_args:
                        real_args = (
                            tuple(tool_args["args"]) if isinstance(tool_args["args"], list) else tool_args["args"]
                        )
                        real_kwargs = tool_args.get("kwargs", {})
                    else:
                        # parse e.g. '{"prompt": "how are you"}'
                        real_args = []
                        real_kwargs = tool_args
                    tool_result = tool_func(*real_args, **real_kwargs)
                except Exception as e:
                    tool_result = str(e)
                tool_result = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                tool_response = {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}
                tool_results.append(tool_result)
                tool_prompts.append(tool_response)
                self._log_events(
                    'toolcall',
                    conversation_id,
                    {
                        'name': tool_name,  # fmt:asis
                        'too_call_id': tool_id,
                        'arguments': tool_args,
                        'result': str(tool_result),
                    },
                )
            else:
                # invalid tool call
                tool_result = 'tool call was invalid'
                tool_response = {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}
                tool_results.append(tool_result)
                tool_prompts.append(tool_response)
                self._log_events(
                    'error',
                    conversation_id,
                    {
                        'name': tool_name,  # fmt:asis
                        'too_call_id': tool_id,
                        'arguments': tool_args,
                        'result': str(tool_result),
                    },
                )
        results = {'tool_calls': tool_calls, 'tool_prompts': tool_prompts, 'tool_results': tool_results}
        return results, tool_prompts
