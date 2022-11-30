from unittest.mock import MagicMock

from django.test import TestCase, RequestFactory

from omegaweb.middleware import RequestTimingMiddleware


class MiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_requestid_middleware(self):
        request = self.factory.get('/')
        get_response = MagicMock()
        get_response.return_value = MagicMock()
        mw = RequestTimingMiddleware(get_response)
        mw(request)
