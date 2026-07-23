"""Integration test that exercises the logic defined in guardrails.py __main__ block."""

import unittest
from omegaml.backends.guardrails import GuardrailPolicy


class GuardrailPolicyTests(unittest.TestCase):
    """A single testcase that mirrors every line of logic from guardrails.py '__main__'."""

    def test_state_flow(self):
        # ------------------------------------------------------------------
        # 1.  SCANNERS dict — copied verbatim from __main__ (the scanner
        #     lambdas inspect the *last* message in the list).
        # ------------------------------------------------------------------
        SCANNERS = {
            'haiku_in_prompt': lambda policy, messages: ('haiku' in messages[-1]['content'], 'haiku not in messages'),
            'evil_in_prompt': lambda policy, messages: ('evil' not in messages[-1]['content'], 'evil in messages'),
            'bad_in_prompt': lambda policy, messages: ('bad' not in messages[-1]['content'], 'bad in messages'),
        }

        # ------------------------------------------------------------------
        # 2.  guardrails() factory — copied verbatim from __main__.
        #     Builds a policy with two states (converse → stop).
        # ------------------------------------------------------------------
        def guardrails(model=None):
            policy = GuardrailPolicy('mypolicy', model)
            # -- converse guardrails --
            policy.add_guardrail(state='converse', phase='all', fn='haiku_in_prompt')
            policy.add_guardrail(state='converse', phase='all', fn='evil_in_prompt')

            # converse → stop transition
            policy.add_transition(from_state='converse', to_state='stop', intent='finalize')
            policy.add_eval(state='converse', kind='intent', fn=lambda policy, messages: ('finalize', {}))
            policy.add_eval(state='converse', kind='state', fn=lambda policy, messages: ('stop', {}))

            # stop-state guardrail (checks after entering 'stop')
            policy.add_guardrail(state='stop', phase='all', fn='bad_in_prompt')
            return policy

        # ------------------------------------------------------------------
        # 3.  Scenario A — the *exact* __main__ call which must raise:
        #     last-content = "Write an evil haiku about summer."
        #       haiku_in_prompt  → True  (haiku IS present)
        #       evil_in_prompt   → False (evil IS present → rail fails!)
        # ------------------------------------------------------------------
        messages_A = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write an evil haiku about summer."},
        ]
        policy_A = guardrails()
        policy_A.scanners = SCANNERS  # mirrors: "loaded by omegaml from…"
        with self.assertRaises(ValueError) as ctx_A:
            policy_A.eval(messages_A)
        exc_str = str(ctx_A.exception)
        self.assertIn('converse', exc_str)  # rail fired while in 'converse' state
        self.assertIn('evil in messages', exc_str)  # evil_in_prompt failed (reason='evil in messages')

        # ------------------------------------------------------------------
        # Scenario B — happy path: keep the same intent/state evals but
        # remove 'evil' so haiku_in_prompt passes AND evil_in_prompt passes.
        # ------------------------------------------------------------------
        messages_B = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Now write a nice haiku about summer."},  # no 'evil', still has 'haiku'
        ]
        policy_B = guardrails()
        policy_B.scanners = SCANNERS
        result_B = policy_B.eval(messages_B)

        self.assertTrue(result_B, 'eval returned truthy on success')
        self.assertEqual(policy_B.state, 'stop', 'intent + state lambdas drove transition')
        self.assertIn(
            'finalize', policy_B.context.get('intents', []), "context.intents should contain the fired intent"
        )

        # ------------------------------------------------------------------
        # 4.  post-transition guardrail (state == 'stop'):
        #     last-content = "A good person lives long and prosper."   (no 'bad')
        #       bad_in_prompt → True  ('bad' not present)  → rail passes
        # ------------------------------------------------------------------
        messages_B.append({"role": "assistant", "content": "A good person lives long and prosper."})
        result_B2 = policy_B.eval(messages_B)
        self.assertTrue(result_B2, 'no new rails should make the second eval fail')

        # ------------------------------------------------------------------
        # 5.  data property (read + write), copied verbatim from __main__:
        # ------------------------------------------------------------------
        _data_dict = policy_B.data  # read → {'state': ..., 'context': ...}
        self.assertIn('state', _data_dict)
        self.assertIn('context', _data_dict)

        policy_B.data = policy_B.data  # write (round-trip from __main__)
        self.assertEqual(policy_B.state, 'stop')  # state survived round-trip

        # ------------------------------------------------------------------
        # 6.  __repr__ and the final "policy" reference used in __main__.
        #     (the repr has a known typo but must not crash)
        # ------------------------------------------------------------------
        repr_str = repr(policy_B)  # calls __repr__ / is printed as `policy`
        self.assertIn('mypolicy', repr_str)


if __name__ == '__main__':
    unittest.main()
