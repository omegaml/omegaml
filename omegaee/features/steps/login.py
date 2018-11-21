import re

from behave import *

import omegaml
from omegaee.features.util import uri, find_user_apikey


@given('we have a new user')
def given_new_user(ctx):
    br = ctx.browser
    br.visit(uri(br, '/admin/post_office/email/'))
    # select email
    el = br.find_by_text(ctx.feature.username)
    el.find_by_xpath('../th[@class="field-id"]/a').click()
    # read confirmation url
    text = br.find_by_id('id_message').text
    regex = r".*go.to.(.*)"
    # signout of admin
    br.click_link_by_text('Log out')
    # execution formation
    confirm_url = re.findall(regex, text)[0]
    br.visit(confirm_url)
    assert br.is_text_present('Confirm E-mail Address', wait_time=2)
    br.find_by_text('Confirm').click()
    assert br.is_text_present('Login', wait_time=2)


@when('we log in')
def login_new_user(ctx):
    br = ctx.browser
    br.visit(uri(br, '/accounts/login'))
    br.fill('login', ctx.feature.username)
    br.fill('password', ctx.feature.password)
    br.click_link_by_text('Login ')


@then('the site shows the dashboard')
def site_shows_dashboard(ctx):
    br = ctx.browser
    assert br.is_text_present('Your apps', wait_time=2)
    assert br.is_text_present('omegaml')

@then('we log out')
def log_out(ctx):
    br = ctx.browser
    br.visit(uri(br, '/accounts/logout'))
    for el in br.find_by_text('Sign Out'):
        el.click()
    assert br.is_text_present('sign in', wait_time=5)


@then('we can get an omega instance')
def get_omgega_instance(ctx):
    br = ctx.browser
    # check we can get a new omegaml instance
    userid, apikey = find_user_apikey(br)
    # view = False => get a setup with public URLs
    om = omegaml.setup(userid, apikey, api_url=ctx.web_url, view=False)
    assert om.datasets.mongodb is not None
    # check it actually works
    assert len(om.datasets.list()) == 0
    om.datasets.put({'foo': 'bar'}, 'test')
    assert len(om.datasets.list()) == 1
    data = om.datasets.get('test')
    assert data[0] == {'foo': 'bar'}
    # logout
    br.visit(uri(br, '/accounts/logout'))
    for el in br.find_by_text('Sign Out'):
        el.click()
    assert br.is_text_present('sign in', wait_time=5)


@given('we are not logged in')
def not_logged_in(ctx):
    br = ctx.browser
    br.visit(uri(br, '/accounts/logout'))
    for el in br.find_by_text('Sign Out'):
        el.click()
    assert br.is_text_present('sign in', wait_time=5)


@then('we can load the jupyter notebook')
def load_jupyter_notebook(ctx):
    br = ctx.browser
    assert br.is_element_present_by_text('Profile', wait_time=5)
    br.click_link_by_text('Profile')
    userid, apikey = find_user_apikey(br)
    br.click_link_by_text('Dashboard')
    el = br.find_by_text('Notebook').first
    br.visit(el['href'])
    assert br.is_element_present_by_id('username_input', wait_time=5)
    br.find_by_id('username_input').first.fill(userid)
    br.find_by_id('password_input').first.fill(apikey)
    br.click_link_by_id('login_submit')
    assert br.is_element_present_by_id('ipython-main-app', wait_time=5)
    # check that there is actually a connection
    assert not br.is_text_present('Server error: Traceback', wait_time=5)
    assert not br.is_text_present('Connection refuse', wait_time=5)
