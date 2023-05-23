def make_base():
    # this avoids unittest discovery of SignupResourceTests
    # unittest.skip() does not seem to work with unittest
    from landingpage.tests.api.test_signup import SignupResourceTests
    return SignupResourceTests


class SignupApi(make_base()):
    fixtures = ['landingpage']
