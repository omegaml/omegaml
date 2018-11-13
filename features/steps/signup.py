import os
from uuid import uuid4

import yaml
from behave import *

from features.util import uri


@given("we have the site deployed")
def site_deployed(ctx):
    url = ctx.web_url
    br = ctx.browser
    br.visit(url)
    assert br.is_text_present('sign in'), "expected landing page with <sign in> link"


@when("we signup a new user")
def signup_user(ctx):
    br = ctx.browser
    br.click_link_by_text('sign in')
    assert br.is_text_present('Sign up here', wait_time=2), "Expecting link to <Sign up here>"
    br.visit(uri(br, '/accounts/signup'))
    assert br.is_text_present('Create account', wait_time=2)
    ctx.feature.username = '{}@omegaml.io'.format(uuid4().hex)
    ctx.feature.password = 'test9test9'
    br.fill('email', ctx.feature.username)
    br.fill('password1', ctx.feature.password)
    br.click_link_by_text('Create account')
    assert br.is_text_present('Verify Your E-mail Address', wait_time=5)


@then("the site sends out a registration email")
def site_registration_email(ctx):
    br = ctx.browser
    # login to admin
    br.visit(uri(br, '/admin'))
    assert br.is_text_present('Django administration', wait_time=2)
    assert br.is_text_present('Password:')
    secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
    with open(secrets) as fin:
        secrets = yaml.load(fin)
    br.fill('username', secrets['admin_user'])
    br.fill('password', secrets['admin_password'])
    br.find_by_value('Log in').first.click()
    # open emails sent
    assert br.is_text_present('Django administration', wait_time=2)
    br.visit(uri(br, '/admin/post_office/email/'))
    assert br.is_text_present(ctx.feature.username, wait_time=2)


