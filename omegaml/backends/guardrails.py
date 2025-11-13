from cachetools import TTLCache, cached
from itertools import chain

from omegaml.backends.virtualobj import virtualobj
from omegaml.util import tryOr

import logging

logger = logging.getLogger(__name__)

session_cache = TTLCache(maxsize=100, ttl=60)


@virtualobj
class GuardrailPolicy:
    """Represents a guardrail policy for evaluating state transitions and validating messages against rules and constraints."""

    def __init__(self, name, model=None, rules=None, state=None, context=None, registry=None):
        """Initialize a GuardrailPolicy instance.

        Args:
            name (str): Name of the policy.
            model (Optional[Any]): Optional model configuration.
            rules (Optional[dict]): Dictionary of rules. Defaults to empty dict if None.
            state (Optional[str]): Initial state ID. Defaults to 'converse'.
            context (Optional[dict]): Context dictionary. Defaults to empty dict if None.
            registry (Optional[dict]): Registry for function names. Defaults to empty dict if None.
        """
        self.name = name
        self.model = model
        self.rules = rules or {}
        self.state = state or "converse"
        self.context = context or {}
        self.add_eval("converse", "intent", lambda messages, **kwargs: ("converse", {}))
        self.add_eval("converse", "state", lambda messages, **kwargs: ("converse", {}))
        self.add_transition("converse", "converse", "converse")
        self.registry = registry or {}
        # self.add_eval('converse', 'state', lambda policy, messages: ('converse', {})),

    def __repr__(self):
        """Return a string representation of the GuardrailPolicy instance."""
        return f"GuardrailPolicy({self.name=}, {self.state=})"

    def __call__(self, messages, step=None, model=None):
        # shim for GuardrailPolicy.eval()
        # -- achieves compatibility with guardrail functions
        # -- enables a GuardrailPolicy() instance to be stored as a virtualobj
        return self.eval(messages, step=step, model=model)

    @property
    def data(self):
        """Retrieve the current state and context data.

        Returns:
            dict: Dictionary containing 'state' and 'context'.
        """
        return {"state": self.state, "context": self.context}

    @data.setter
    def data(self, data):
        """Update the current state and context from a dictionary.

        Args:
            data (dict): Dictionary containing 'state' and 'context' keys.
        """
        self.state = data["state"]
        self.context = data["context"]

    def add_state(self, stateid):
        """Initialize a rule set for a given state ID.

        Creates a new entry in the rules dictionary with default intent, state,
        allowed transitions, and rails if it does not already exist.

        Args:
            stateid (str): The identifier for the state to initialize.
        """
        self.rules[stateid] = {
            "intent": [
                # fn(messages, step=, model=, policy=) => intent, context
            ],
            "state": [
                # fn(messages, step=, model=, policy=) => next_state, context
            ],
            "allowed": {
                # intent => [to_state, ...]
            },
            "rails": {  # kind: fn(messages, step=, model=, policy=) => (bool, 'reason') or raise
                "all": [lambda messages, **kwargs: (True, "ok")]
            },
        }

    def add_eval(self, state, kind, fn):
        """Append a function to a specific evaluation category in a state's rules.

        Args:
            state (str): The identifier of the state to modify.
            kind (str): The evaluation category (e.g., 'intent', 'state').
            fn (Callable): The callable function to append.
        """
        self.add_state(state) if state not in self.rules else None
        self.rules[state][kind].append(fn)

    def add_transition(self, from_state, to_state, intent):
        """Add an allowed transition for a specific intent between two states.

        Ensures both from_state and to_state exist in the rules, then registers
        the intent as a valid transition to the to_state.

        Args:
            from_state (str): The current state ID.
            to_state (str): The target state ID.
            intent (str): The intent triggering this transition.
        """
        self.add_state(from_state) if from_state not in self.rules else None
        self.add_state(to_state) if to_state not in self.rules else None
        self.rules[from_state]["allowed"].setdefault(intent, []).append(to_state)

    def add_guardrail(self, state, phase, fn):
        """Add a single guardrail function to a specific phase for a state.

        Args:
            state (str): The identifier of the state to modify.
            phase (str): The phase or step key (e.g., 'all').
            fn (str|Callable): The callable guardrail function, or a name in the registry.
        """
        self.add_state(state) if state not in self.rules else None
        rails = self.rules[state]["rails"].setdefault(phase, [])
        rails.append(fn)

    def add_guardrails(self, state, phase, fns):
        """Add multiple guardrail functions to a specific phase for a state.

        Args:
            state (str): The identifier of the state to modify.
            phase (str): The phase or step key (e.g., 'all').
            fns (Iterable[Callable]): An iterable of callable guardrail functions.
        """
        for fn in fns:
            self.add_guardrail(state, phase, fn)

    def eval(self, messages, step=None, model=None):
        """Evaluate messages against the current policy's rules and transition if valid.

        Applies rails, evaluates intents, updates context, checks allowed state
        transitions, and optionally re-applies rails after a state change. Note that rails defined for
        step 'all' will always be applied.

        Args:
            messages (list): The input messages to evaluate.
            step (Optional[str]): Optional step phase for evaluating rails. Defaults to 'all'.

        Returns:
            bool: Always returns True upon successful evaluation.

        Raises:
            ValueError: If the evaluated intent is not allowed for the requested state transition.
        """
        step = step or "all"
        self.model = model or self.model
        start_state = self.state
        rule = self.rules[self.state]
        # apply rails
        self.context['eval'] = f'rails:{self.state}'
        [self.apply_rails(self.state, step, messages) for step in {step, 'all'}]
        # eval intents
        self.context['eval'] = f'intent:{self.state}'
        all_intents = self.context.setdefault("intents", [])
        step_intents = []
        for evalfn in rule["intent"]:
            evalfn = self.registry.get(evalfn, evalfn)
            intent, data = self._callfn(evalfn, messages, step=step, model=model, policy=self)
            all_intents.append((step, intent, data))
            step_intents.append(intent)
            self.context.update(data)
        self.context.update(intents=all_intents, step_intents=step_intents)
        # eval state and transition
        self.context['eval'] = f'state:{self.state}'
        states = self.context.setdefault("states", [])
        for evalfn in rule["state"]:
            evalfn = self.registry.get(evalfn, evalfn)
            next_state, data = self._callfn(evalfn, messages, step=step, model=model, policy=self)
            allowed_rules = rule["allowed"] or {}
            allowed_transitions = list(chain.from_iterable(allowed_rules.get(intent, []) for intent in step_intents))
            if next_state in allowed_transitions:
                states.append((step, self.state, next_state, data))
                self.state = next_state
                self.context.update(data)
                continue
            else:
                raise ValueError(f"{intent=} not allowed from {self.state=} to {next_state=}")
        # optionally apply guardrails again
        if self.state != start_state:
            self.context['eval'] = f'rails:{self.state}'
            [self.apply_rails(self.state, step, messages) for step in {step, 'all'}]
        return True

    def apply_rails(self, state, step, messages):
        """Apply guardrail functions for a given state and step phase.

        Iterates through rail functions for the specified step, executes them,
        and raises an error if any rail returns False.

        Args:
            state (str): The identifier of the state to check rails for.
            step (str): The step phase key to filter rails.
            messages (list): The input messages passed to each rail function.

        Returns:
            bool: Always returns True upon completion.

        Raises:
            ValueError: If any rail function indicates failure with a reason.
        """
        rails = self.rules[state]["rails"]
        for railfn in rails.get(step) or []:
            railfn = self.registry.get(railfn, railfn)
            result = self._callfn(railfn, messages, step=step, model=self.model, policy=self) if railfn else True
            expanded_result = (result, 'ok') if result else (result, 'not ok')
            result = result if isinstance(result, tuple) else expanded_result
            rail_ok, reason = result if result is not None else (True, "ok")
            if not rail_ok:
                raise ValueError(f"messages in {state=} triggered rail for {step=} due to {reason=}")  # fmt: off
        return True

    def _callfn(self, fn, *args, **kwargs):
        """Validate and invoke a callable function with provided arguments.

        Args:
            fn (Callable): The callable to invoke.
            *args (tuple): Positional arguments passed to the callable.
            **kwargs (dict): Keyword arguments passed to the callable.

        Returns:
            The result of calling fn(*args, **kwargs).

        Raises:
            AssertionError: If fn is not callable.
        """
        assert callable(fn), f"{fn} is not a callable type={type(fn)}. Does it exist in om.models?"
        return fn(*args, **kwargs)

    def add_scanner(self, fn, name=None):
        """Register a named function in the scanner registry.

        Args:
            fn (Callable): The callable function to register.
            name (str): optional, the identifier for the scanner. If no name is given,
              it will be derived from the callable
        """

        def getname(fn):
            return getattr(fn, '__name__', None) or tryOr(
                lambda: fn.__class__.__name__.lower() if repr(fn).startswith('<') else repr(fn), repr(fn)
            )

        name = name or getname(fn)
        self.registry[name] = fn

    @property
    def scanners(self):
        """Retrieve the current scanner registry.

        Returns:
            dict: The dictionary mapping scanner names to functions.
        """
        return self.registry

    @scanners.setter
    def scanners(self, fns):
        """Update the scanner registry with a new dictionary of functions.

        Args:
            fns (dict|list): Either a dictionary mapping names to callable functions or a
               a list of callables. For the list of functions, fn.__name__ is used as the

        """
        if isinstance(fns, dict):
            self.registry = {name: fn for name, fn in fns.items()}
        else:
            self.registry = {}
            [self.add_scanner(fn) for fn in fns]

    def load(self):
        import omegaml as om

        self.scanners = {
            name.replace('policy/scanners/', '', 1): om.models.get(name) for name in om.models.list('policy/scanners/*')
        }

    @cached(session_cache)
    def create(self, key, fn, *args, **kwargs):
        """Return an LRU-cached version of the function result.

        The result is cached based on the provided key using a TTLCache.

        Args:
            key (Any): Cache key for this invocation.
            fn (Callable): Function to wrap and invoke.
            *args (tuple): Positional arguments passed to fn.
            **kwargs (dict): Keyword arguments passed to fn.

        Returns:
            The return value of fn(*args, **kwargs) or its cached version.
        """
        return fn(*args, **kwargs)
