import os
from http import HTTPStatus
from time import sleep

import requests
from behave import then, when


@when(u'we deploy app {setupdir} as {appname}')
def step_impl(ctx, setupdir, appname):
    om = ctx.feature.om
    om.scripts.put('pkg://{}'.format(os.path.abspath(setupdir)), appname)


@then(u'we can access the app at {uri}')
def step_impl(ctx, uri):
    apps_url = '{}/{}'.format(ctx.web_url, '/apps')
    app_url = '{}/{}'.format(ctx.web_url, uri.format(user=ctx.feature.om_userid))
    # TODO login to apphub using om.feature.om_user/apikey, then start app
    br = ctx.browser
    br.visit(apps_url)
    br.fill('username', ctx.feature.om_userid)
    br.fill('password', ctx.feature.om_apikey)
    br.find_by_css('button.btn').click()
    br.find_by_css('a i.fa.fa-play').click()
    # wait until app is started, then see if we can get it
    sleep(10)
    br.visit(app_url)
    assert br.is_text_present('Hello Dash', wait_time=15)


