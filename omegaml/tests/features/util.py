import warnings

import os

import yaml
from selenium.webdriver.common.keys import Keys
from time import sleep
from urllib.parse import quote, urlparse, urlunparse

istrue = lambda v: (
    (v.lower() in ('yes', '1', 'y', 'true', 't'))
    if isinstance(v, str) else bool(v)
)
isfalse = lambda v: not istrue(v)


def uri(browser, uri):
    """ given a browser, replace the path with uri """
    url = browser.url
    parsed = list(urlparse(url))
    parsed[2] = uri
    return urlunparse(parsed)


ACTIVATE_CELL = Keys.ESCAPE, Keys.ENTER, Keys.ENTER
EXEC_CELL = Keys.SHIFT, Keys.ENTER
ADD_CELL_BELOW = Keys.ESCAPE, 'b'
SAVE_NOTEBOOK = Keys.CONTROL, 's'
SHOW_LAUNCHER = Keys.SHIFT, Keys.CONTROL, 'l'
RESTART_CELL = Keys.ESCAPE, '0', '0', Keys.ENTER
FILE_BROWSER = Keys.CONTROL, Keys.SHIFT, 'f'


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
    def nbcell(self):
        return self.browser.find_by_css('.lm-Widget.jp-Notebook').first

    @property
    def active(self):
        el = self.browser.driver.switch_to.active_element
        el.type = el.send_keys
        return el

    @property
    def jupyter_home(self):
        br = self.browser
        br.windows.current = br.windows[0]
        sleep(1)
        return self

    @property
    def file_browser(self):
        br = self.browser
        if not br.is_text_present('Last Modified'):
            self.active.type(FILE_BROWSER)
        return self

    @property
    def last_notebook(self):
        br = self.browser
        br.windows.current = br.windows[-1]
        return self

    def login(self):
        br = self.browser
        maxwait = 15
        is_hub, is_nb = False, False
        while maxwait > 0:
            is_hub = br.is_text_present('JupyterHub', wait_time=1)
            is_nb = br.is_text_present('Password', wait_time=1)
            if is_hub or is_nb:
                break
            maxwait -= 1
            sleep(1)

        if is_hub:
            login_required = br.is_element_present_by_id('username_input', wait_time=30)
            if login_required:
                self.login_hub()
        elif is_nb:
            # fallback to juypter notebook
            login_required = br.is_text_present('Password', wait_time=15)
            login_required = login_required or br.is_text_present('token', wait_time=15)
            if login_required:
                self.login_nb()
        else:
            # no login required
            pass

    def login_hub(self):
        br = self.browser
        br.find_by_id('username_input').first.fill(self.user)
        br.find_by_id('password_input').first.fill(self.password)
        br.find_by_id('login_submit').click()
        br.visit(jburl(br.url, self.user, nbstyle='tree'))
        assert br.is_element_present_by_id('ipython-main-app', wait_time=60)
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=15)
        assert not br.is_text_present('Connection refuse', wait_time=15)

    def login_nb(self):
        br = self.browser
        assert br.is_element_present_by_id('jupyter-main-app', wait_time=10)
        br.find_by_id('password_input').fill(self.password)
        br.find_by_id('login_submit').click()
        br.visit(jburl(br.url, '', nbstyle='tree'))
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=10)
        assert not br.is_text_present('Connection refuse', wait_time=10)

    def create_folder(self, name=''):
        """
        create a folder
        """
        br = self.browser
        self.jupyter_home
        self.file_browser
        br.find_by_xpath("//button[@data-command='filebrowser:create-new-directory']").first.click()
        sleep(2)
        self.active.type(name + Keys.ENTER)
        sleep(2)

    def create_notebook(self, folder=None):
        """
        create a new notebook
        """
        br = self.browser
        self.jupyter_home
        self.file_browser
        self.body.type(SHOW_LAUNCHER)
        # TODO this is rather brittle. find a better way
        # this uses the visible launcher's first item
        br.find_by_text('Python 3 (ipykernel)')[-2].click()
        sleep(2)
        self.last_notebook
        return self

    def open_notebook(self, name, retry=5):
        self.jupyter_home
        self.file_browser
        br = self.browser
        while retry:
            found = br.is_text_present(name)
            retry = retry - 1 if not found else 0
            sleep(1)
        item = [el for el in br.find_by_css('.jp-DirListing-itemText') if el.value.startswith(name)][0]
        item.double_click()
        sleep(2) # wait for the notebook to open
        self.last_notebook # switch to last window
        return self

    def restart(self, wait=False):
        br = self.browser
        self.nbcell.type(RESTART_CELL)
        sleep(1)
        if wait:
            while self.kernel_busy:
                sleep(1)

    def run_all_cells(self, wait=False):
        br = self.browser
        assert br.is_element_present_by_text('Run', wait_time=30)
        br.find_by_text('Run')[0].click()
        sleep(1)
        # use -1 to ensure we have an interactable element
        br.find_by_text('Run All Cells')[-1].click()
        if wait:
            while self.kernel_busy:
                sleep(1)

    @property
    def kernel_busy(self):
        br = self.browser
        status = br.find_by_css('.jp-Notebook-ExecutionIndicator').first['data-status']
        busy = status != 'idle'
        return busy

    def open_folder(self, folder=None):
        br = self.browser
        self.file_browser
        item = br.find_by_css('.jp-DirListing-itemText').find_by_text(folder).first
        item.double_click()
        return self

    def _clean_code(self, code):
        return tuple('\n'.join(line.strip() for line in code.split('\n')))

    def current_cell_exec(self, code):
        self.nbcell.type(ACTIVATE_CELL + self._clean_code(code) + EXEC_CELL)

    def new_cell_exec(self, code):
        self.nbcell.type(ADD_CELL_BELOW + ACTIVATE_CELL + self._clean_code(code) + EXEC_CELL)

    def current_cell_output(self):
        return self.nbcell.find_by_css('.jp-OutputArea-output pre')[-1].text

    def save_notebook(self):
        self.nbcell.type(SAVE_NOTEBOOK)
        br = self.browser
        if br.is_text_present('Rename'):
            br.find_by_text('Rename')[0].click()


def get_admin_secrets(scope=None, keys=None):
    secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
    with open(secrets) as fin:
        secrets = yaml.safe_load(fin)
        secrets = secrets.get(scope, {}) if scope else secrets
    if keys:
        result = [secrets.get(k) for k in keys]
    else:
        result = secrets
    return result


def jburl(url, userid, **kwargs):
    # provide a users notebook url to lab. we no longer support tree
    if 'nbstyle' in kwargs:
        warnings.warn("nbstyle is no longer supported. we only support lab")
    nbstyle = 'doc'  # simple interface (in lab: ctrl-shift-d)
    parsed = urlparse(url)
    baseurl = '{parsed.scheme}://{parsed.netloc}'.format(**locals())
    if userid:
        jburl = '{baseurl}/user/{userid}/{nbstyle}'
    else:
        jburl = '{baseurl}/{nbstyle}'
    return jburl.format(**locals()).replace('//', '/')
