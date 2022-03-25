from landingpage.models import ServicePlan


def make_base():
    # this avoids unittest discovery of SignupResourceTests
    # unittest.skip() does not seem to work with unittest
    from landingpage.tests.api.test_signup import SignupResourceTests
    return SignupResourceTests


class SignupApi(make_base()):
    def setUp(self):
        super(SignupApi, self).setUp()
        ServicePlan.objects.create(name='omegaml')

    def url(self, pk=None):
        _url = super(SignupApi, self).url(pk=pk)
        return '/admin' + _url
