import os

import yaml
from selenium.webdriver.common.keys import Keys
from time import sleep
from urllib.parse import quote, urlparse

istrue = lambda v: (
    (v.lower() in ('yes', '1', 'y', 'true', 't'))
    if isinstance(v, str) else bool(v)
)
isfalse = lambda v: not istrue(v)


def uri(browser, uri):
    """ given a browser, replace the path with uri """
    from six.moves.urllib.parse import urlparse, urlunparse
    url = browser.url
    parsed = list(urlparse(url))
    parsed[2] = uri
    return urlunparse(parsed)


ACTIVATE_CELL = Keys.ESCAPE, Keys.ENTER
EXEC_CELL = Keys.SHIFT, Keys.ENTER
ADD_CELL_BELOW = Keys.ESCAPE, 'b'
SAVE_NOTEBOOK = Keys.CONTROL, 's'


class Notebook:
    """
    A simple driver for the notebook
    """

    def __init__(self, browser, user='admin', password='test'):
        self.browser = browser
        self.user = user
        self.password = password
        try:
            alert = browser.get_alert()
        except:
            pass
        else:
            if alert is not None:
                alert.accept()

    @property
    def body(self):
        return self.browser.find_by_css('body').first

    @property
    def jupyter_home(self):
        br = self.browser
        br.windows.current = br.windows[0]
        sleep(1)
        return self

    @property
    def last_notebook(self):
        br = self.browser
        br.windows.current = br.windows[-1]
        return self

    def login(self):
        br = self.browser
        if br.is_text_present('JupyterHub', wait_time=15):
            login_required = br.is_element_present_by_id('username_input', wait_time=30)
            if login_required:
                self.login_hub()
        else:
            # fallback to juypter notebook
            login_required = br.is_text_present('Password', wait_time=15)
            login_required |= br.is_text_present('token', wait_time=15)
            if login_required:
                self.login_nb()

    def login_hub(self):
        br = self.browser
        br.find_by_id('username_input').first.fill(self.user)
        br.find_by_id('password_input').first.fill(self.password)
        br.click_link_by_id('login_submit')
        br.visit(jburl(br.url, self.user, nbstyle='tree'))
        assert br.is_element_present_by_id('ipython-main-app', wait_time=60)
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=15)
        assert not br.is_text_present('Connection refuse', wait_time=15)

    def login_nb(self):
        br = self.browser
        assert br.is_element_present_by_id('ipython-main-app', wait_time=10)
        br.find_by_id('password_input').fill(self.password)
        br.find_by_id('login_submit').click()
        br.visit(jburl(br.url, '', nbstyle='tree'))
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=10)
        assert not br.is_text_present('Connection refuse', wait_time=10)

    def create_folder(self):
        """
        create a folder
        """
        br = self.browser
        self.jupyter_home
        br.find_by_id('new-dropdown-button').click()
        br.find_by_text('Folder').click()
        sleep(2)

    def create_notebook(self, folder=None):
        """
        create a new notebook
        """
        br = self.browser
        self.jupyter_home
        br.find_by_id('new-dropdown-button').click()
        br.find_by_text('Python 3').click()
        sleep(2)
        self.last_notebook
        return self

    def open_notebook(self, name, retry=5):
        self.jupyter_home
        br = self.browser
        # FIXME sometimes it takes long for the nb to appear why?
        while retry:
            br.reload()
            found = br.is_text_present(name, wait_time=60)
            retry = 0 if found else retry
        item = br.find_link_by_partial_text(name)
        item.click()
        sleep(2)
        self.last_notebook
        return self

    def restart(self, wait=False):
        br = self.browser
        assert br.is_element_present_by_text('Cell', wait_time=60)
        br.find_link_by_text('Kernel', )[0].click()
        sleep(1)
        br.find_link_by_text('Restart')[0].click()
        if wait:
            busy = True
            while busy:
                sleep(5)
                busy = br.is_element_present_by_css('#kernel_indicator_icon.kernel_busy_icon')

    def run_all_cells(self, wait=False):
        br = self.browser
        assert br.is_element_present_by_text('Cell', wait_time=30)
        br.find_link_by_text('Cell', )[0].click()
        sleep(1)
        br.find_link_by_text('Run All')[0].click()
        if wait:
            busy = True
            while busy:
                sleep(5)
                busy = br.is_element_present_by_css('#kernel_indicator_icon.kernel_busy_icon')

    def open_folder(self, folder=None):
        br = self.browser
        folder = quote(folder.encode('utf-8'))
        item = br.find_link_by_href('/tree/{folder}'.format(**locals()))[0]
        item.click()
        return self

    def _clean_code(self, code):
        return tuple('\n'.join(line.strip() for line in code.split('\n')))

    def current_cell_exec(self, code):
        self.body.type(ACTIVATE_CELL + self._clean_code(code) + EXEC_CELL)

    def new_cell_exec(self, code):
        self.body.type(ADD_CELL_BELOW + ACTIVATE_CELL + self._clean_code(code) + EXEC_CELL)

    def current_cell_output(self):
        return self.body.find_by_css('.output_subarea pre')[-1].text

    def save_notebook(self):
        self.body.type(SAVE_NOTEBOOK)


def get_admin_secrets(scope=None, keys=None):
    secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
    with open(secrets) as fin:
        secrets = yaml.safe_load(fin)
        secrets = secrets[scope] if scope else secrets
    if keys:
        result = [secrets.get(k) for k in keys]
    else:
        result = secrets
    return result

def jburl(url, userid, nbstyle='tree'):
    # provide a users notebook url to lab (new style) or tree (old style) notebook
    parsed = urlparse(url)
    baseurl = '{parsed.scheme}://{parsed.netloc}'.format(**locals())
    if userid:
        jburl = '{baseurl}/user/{userid}/{nbstyle}'
    else:
        jburl = '{baseurl}/{nbstyle}'
    return jburl.format(**locals()).replace('//', '/')
