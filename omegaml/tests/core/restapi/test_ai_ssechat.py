import json
import unittest
from hashlib import pbkdf2_hmac
from jose import jwe
from jose.exceptions import JWEError
from uuid import uuid4

from omegaml import Omega
from omegaml.backends.restapi.streamable import StreamableResourceMixin
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.tests.util import OmegaTestMixin


class SSEServerTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()

    def test_streamable_inline(self):
        resource = StreamableResourceMixin()
        om = resource.om = self.om
        stream = om.streams.get('.system/complete/messages')
        producer_events = [
            {
                'message': 'hello world',
            },
        ]
        for event in producer_events:
            stream.append(event)
        # mark end of streaming
        stream.append({
            'finish_reason': 'stop',
        })
        result = resource.prepare_streaming_result(stream='messages', streamer='inline')
        received_events = list(result)
        self.assertEqual(len(received_events), len(producer_events))
        self.assertTrue(all(ev in producer_events for ev in received_events))

    def test_streamable_ssechat(self):
        resource = StreamableResourceMixin()
        om = resource.om = self.om
        result = resource.prepare_streaming_result(stream='messages', streamer='ssechat')
        self.assertIsInstance(result, (list, tuple))
        # verify we get a redirect
        body, status_code, headers, cookies = result
        self.assertEqual(status_code, 302)
        self.assertEqual(headers.get('Location'), om.defaults.OMEGA_EVENTS_STREAMER_URL)
        print(cookies)
        # verify the cookies are encrypted
        self.assertIn('token', cookies)
        self.assertIn('session_id', cookies)
        token = cookies.get('token')
        session_id = cookies.get('session_id')
        token_header = jwe.get_unverified_header(token)
        self.assertEqual(token_header, {'alg': 'dir', 'enc': 'A256GCM'})
        # verify decryption
        # -- use arbitrary key
        with self.assertRaises(JWEError):
            key = uuid4().hex
            contents = json.loads(jwe.decrypt(token, key))
        # -- use actual key
        key = pbkdf2_hmac('sha256', StreamableResourceMixin.SECRET_KEY.encode('utf-8'),
                          str(session_id).encode('utf-8'),
                          StreamableResourceMixin.PBKDF_ITER)
        contents = json.loads(jwe.decrypt(token, key))
        self.assertIsInstance(contents, dict)
        self.assertTrue(set(contents.keys()) >= {'stream', 'userid', 'created'})
        self.assertEqual(contents.get('stream'), 'messages')


if __name__ == '__main__':
    unittest.main()
