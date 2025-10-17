import json
import unittest
from flask import Flask
from hashlib import pbkdf2_hmac
from jose import jwe
from jose.exceptions import JWEError
from unittest.mock import patch
from uuid import uuid4

from omegaml import Omega
from omegaml.backends.restapi.streamable import StreamableResourceMixin
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.server.events.ssechat import bp as ssechat_bp
from omegaml.tests.util import OmegaTestMixin


class SSEServerTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()
        self.app = Flask(__name__)
        self.app.register_blueprint(ssechat_bp)

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

    def test_streamable_ssechat_redirect(self):
        resource = StreamableResourceMixin()
        om = resource.om = self.om
        result = resource.prepare_streaming_result(stream='messages', streamer='ssechat')
        self.assertIsInstance(result, (list, tuple))
        # verify we get a redirect
        body, status_code, headers, cookies = result
        self.assertEqual(status_code, 302)
        self.assertEqual(headers.get('Location'), om.defaults.OMEGA_EVENTS_STREAMER_URL)
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

    def _create_cookies(self):
        # simulate a streaming result using 'ssechat' streamer
        # -- we only do this to get a valid cookie, as if produced the /chat/completions api
        resource = StreamableResourceMixin()
        resource.om = self.om
        result = resource.prepare_streaming_result(stream='messages', streamer='ssechat')
        self.assertIsInstance(result, (list, tuple))
        body, status_code, headers, cookies = result
        return cookies

    def test_ssechat_unauthorized(self):
        cookies = self._create_cookies()
        # verify ssechat events response
        # a) no cookies set
        # -- expect 401
        with self.app.test_client() as client:
            response = client.get('/events/chat/completions')
            self.assertTrue(response.status_code, 401)

    def test_ssechat_valid(self):
        # b) cookies set correctly
        # -- expect 201, a valid stream
        cookies = self._create_cookies()
        with self.app.test_client() as client:
            with patch('omegaml.server.events.ssechat.stream_result') as stream_result:
                for k, v in cookies.items():
                    client.set_cookie(k, v)
                response = client.get('/events/chat/completions')
                self.assertTrue(response.status_code, 201)
                self.assertTrue(response.mimetype, 'text/event-stream')
                stream_result.assert_called_once_with('messages')

    def test_ssechat_streaming(self):
        cookies = self._create_cookies()
        # c) test streaming actually works
        stream = self.om.streams.get('.system/complete/messages')
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
        with self.app.test_client() as client:
            for k, v in cookies.items():
                client.set_cookie(k, v)
            response = client.get('/events/chat/completions')
            self.assertTrue(response.status_code, 201)
            self.assertTrue(response.mimetype, 'text/event-stream')
            self.assertTrue(response.is_streamed)

            def parse_events(response):
                for chunk in response.iter_encoded():
                    if chunk.startswith(b'data: '):
                        event_data = chunk.replace(b'data: ', b'').split(b'\n\n')[0]
                        event = json.loads(event_data)
                        yield event

            events = list(parse_events(response))
            self.assertEqual(events, [{'message': 'hello world'}])


if __name__ == '__main__':
    unittest.main()
