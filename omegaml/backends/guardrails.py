from cachetools import TTLCache, cached

session_cache = TTLCache(maxsize=100, ttl=60)


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
        self.state = state or 'converse'
        self.context = context or {}
        self.add_state('converse')
        (self.add_eval('converse', 'intent', lambda policy, messages: ('converse', {})),)
        self.registry = registry or {}
        # self.add_eval('converse', 'state', lambda policy, messages: ('converse', {})),

    def __repr__(self):
        """Return a string representation of the GuardrailPolicy instance."""
        return f'GaurdrailPolicy({self.name=}, {self.state=},{self.context=}'

    @property
    def data(self):
        """Retrieve the current state and context data.

        Returns:
            dict: Dictionary containing 'state' and 'context'.
        """
        return {'state': self.state, 'context': self.context}

    @data.setter
    def data(self, data):
        """Update the current state and context from a dictionary.

        Args:
            data (dict): Dictionary containing 'state' and 'context' keys.
        """
        self.state = data['state']
        self.context = data['context']

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

    def add_state(self, stateid):
        """Initialize a rule set for a given state ID.

        Creates a new entry in the rules dictionary with default intent, state,
        allowed transitions, and rails if it does not already exist.

        Args:
            stateid (str): The identifier for the state to initialize.
        """
        self.rules[stateid] = {
            "intent": [
                # fn(policy, messages) => intent, context
            ],
            "state": [
                # fn(policy, messages) => state, context
            ],
            "allowed": {  # intent => to_state
                "converse": ['converse']
            },
            "rails": {  # kind: fn => (bool, 'reason') or raise
                'all': [lambda policy, messages: (True, 'ok')]
            },
        }

    def add_eval(self, state, kind, fn):
        """Append a function to a specific evaluation category in a state's rules.

        Args:
            state (str): The identifier of the state to modify.
            kind (str): The evaluation category (e.g., 'intent', 'state').
            fn (Callable): The callable function to append.
        """
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
        self.rules[from_state]['allowed'][intent] = to_state

    def add_guardrail(self, state, phase, fn):
        """Add a single guardrail function to a specific phase for a state.

        Args:
            state (str): The identifier of the state to modify.
            phase (str): The phase or step key (e.g., 'all').
            fn (Callable): The callable guardrail function.
        """
        self.add_state(state) if state not in self.rules else None
        rails = self.rules[state]['rails'].setdefault(phase, [])
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

    def eval(self, messages, step=None):
        """Evaluate messages against the current policy's rules and transition if valid.

        Applies rails, evaluates intents, updates context, checks allowed state
        transitions, and optionally re-applies rails after a state change.

        Args:
            messages (list): The input messages to evaluate.
            step (Optional[str]): Optional step phase for evaluating rails. Defaults to 'all'.

        Returns:
            bool: Always returns True upon successful evaluation.

        Raises:
            ValueError: If the evaluated intent is not allowed for the requested state transition.
        """
        step = step or 'all'
        start_state = self.state
        rule = self.rules[self.state]
        # apply rails
        self.apply_rails(self.state, step, messages)
        # eval intent and transition state
        intents = self.context.setdefault('intents', [])
        for evalfn in rule['intent']:
            evalfn = self.registry.get(evalfn, evalfn)
            intent, data = self._callfn(evalfn, self, messages)
            intents.append(intent)
            self.context.update(data)
        self.context.update(intents=intents)
        # eval state and transition
        for evalfn in rule['state']:
            evalfn = self.registry.get(evalfn, evalfn)
            next_state, data = self._callfn(evalfn, self, messages)
            allowed = rule['allowed'].get(intent) or []
            if next_state in allowed:
                self.state = next_state
                self.context.update(data)
                continue
            else:
                raise ValueError(f'{intent=} not allowed from {self.state=} to {next_state=}')
        # optionally apply guardrails again
        if self.state != start_state:
            self.apply_rails(self.state, step, messages)
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
        rails = self.rules[state]['rails']
        for railfn in rails.get(step):
            railfn = self.registry.get(railfn, railfn)
            result = self._callfn(railfn, self, messages) if railfn else True
            rail_ok, reason = result if result is not None else (True, "ok")
            if not rail_ok:
                raise ValueError(f'messages in {state=} triggered rail for {step=} due to {reason=}')
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
        assert callable(fn), f"{fn} is not callable type={type(fn)}. Does it exist in om.models?"
        return fn(*args, **kwargs)

    def add_scanner(self, name, fn):
        """Register a named function in the scanner registry.

        Args:
            name (str): The identifier for the scanner.
            fn (Callable): The callable function to register.
        """
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
            fns (dict): A dictionary mapping names to callable functions.
        """
        self.registry = {name: fn for name, fn in fns.items()}
