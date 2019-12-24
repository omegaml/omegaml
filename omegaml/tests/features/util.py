from time import sleep
from urllib.parse import quote

from selenium.webdriver.common.keys import Keys

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

    def __init__(self, browser):
        self.browser = browser
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
        assert br.is_element_present_by_id('ipython-main-app', wait_time=2)
        br.find_by_id('password_input').fill('omegamlisfun')
        br.find_by_id('login_submit').click()
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=2)
        assert not br.is_text_present('Connection refuse', wait_time=2)

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
        retry = 5
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

    def run_all_cells(self, wait=False):
        br = self.browser
        assert br.is_element_present_by_text('Cell', wait_time=5)
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