import json
import uuid
from typing import Any, Callable


def response_for_toolcalls(
    calls: list[tuple[Callable, Any, dict]], results: bool = False, model: str = "gpt-4"
) -> dict:
    """Build an OpenAI-compatible tool_calls response from a list of (func, args, kwargs) tuples.

    Args:
        calls (list[tuple[Callable, Any, dict]]): A list of (function, positional_args, keyword_args) tuples
          representing the operations to convert into tool call requests.
        results (bool): If ``True``, automatically execute the provided functions and attach their serialized
          outputs as ``role='tool'`` messages within the returned ``"tool_results_raw"`` field. Defaults to ``True``.
        model (str): The name of the AI model included in the response metadata. Defaults to ``"gpt-4"``.

    Returns:
        dict: An OpenAI ``chat.completion`` JSON-serializable object containing the assistant ``tool_calls`` and,
            if ``results=True``, the executed raw tool results.
    """

    # ---- step 1: generate the *assistant-side* tool_calls chunk --------
    assistant_tool_calls = []
    for func, args, kwargs in calls:
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        # serialise arguments as a JSON string (exactly what GPT expects)
        json_args = json.dumps(
            {
                **(
                    dict(enumerate(args))
                    if not isinstance(args, tuple | list)
                    else {k: v for k, v in zip(["args", "kwargs"], [args, kwargs])}
                )
            }
        )

        # For standard OpenAI format we want named arguments as JSON:
        # json_args = json.dumps({"args": args, "kwargs": kwargs})

        assistant_tool_calls.append(
            {"id": call_id, "type": "function", "function": {"name": func.__name__, "arguments": json_args}}
        )
    if not results:
        # ---- pure assistant message (no execution) --------------------
        return {
            "id": f"chatcmpl_{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "model": model,
            "created": int(__import__("time").time()),
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": None, "tool_calls": assistant_tool_calls}}
            ],
        }
    # ---- step 2: execute the calls and build *result-side* response ---
    tool_results = []
    for call, (func, args, kwargs) in zip(assistant_tool_calls, calls):
        try:
            if isinstance(args, dict) and "args" in args and "kwargs" in args:
                real_args = tuple(args["args"]) if isinstance(args["args"], list) else args["args"]
                real_kwargs = args.get("kwargs", {})
            else:
                real_args = args
                real_kwargs = kwargs
            result = func(*real_args, **real_kwargs)
        except Exception as exc:
            result = f"Error: {exc}"
        tool_results.append(
            {
                "call_id": call["id"],
                "tool_message": {
                    "tool_call_id": call["id"],
                    "role": "tool",
                    "name": func.__name__,
                    "content": json.dumps({"result": result}) if not isinstance(result, str) else result,
                },
            }
        )
    # ---- build the tool-result chunk to send back as user messages ---
    resp = {
        "id": f"chatcmpl_{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "model": model,
        "created": int(__import__("time").time()),
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": None, "tool_calls": assistant_tool_calls}}
        ],
    }
    if tool_results:
        resp.update({"tool_results_raw": tool_results})  # handy for the caller to forward back


def as_tool_call(fn, *args, **kwargs):
    return fn, args, kwargs


# usage example
if __name__ == "__main__":

    def add(a: int, b: int) -> int:
        return a + b

    def greet(name: str) -> str:
        return f"Hello, {name}!"

    calls = [(add, (10, 20), {}), (greet, (), {"name": "Alice"})]
    response = response_for_toolcalls(calls)
    print(json.dumps(response, indent=2))
