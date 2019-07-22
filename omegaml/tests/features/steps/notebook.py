from time import sleep
from urllib.parse import quote

from behave import when, then
from selenium.webdriver.common.keys import Keys

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
            alert.accept()

    @property
    def body(self):
        return self.browser.find_by_css('body').first

    @property
    def jupyter_home(self):
        br = self.browser
        br.windows.current = br.windows[0]
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

@when(u'we open jupyter')
def open_jupyter(ctx):
    br = ctx.browser
    br.visit(ctx.jynb_url)
    nb = Notebook(br)
    login_required = br.is_text_present('Password', wait_time=2)
    login_required |= br.is_text_present('token', wait_time=2)
    if login_required:
        nb.login()
    nb.jupyter_home

@when(u'we create a notebook')
def step_impl(ctx):
    br = ctx.browser
    nb = Notebook(br)
    nb.create_notebook()
    nb.save_notebook()
    assert not br.is_text_present('error while saving')
    # test code execution
    code = """
    print('hello')
    """.strip()
    nb.current_cell_exec(code)
    sleep(1)
    assert nb.current_cell_output() == 'hello'
    nb.save_notebook()
    assert not br.is_text_present('error while saving')


@when(u'we create a folder')
def create_folder(ctx):
    br = ctx.browser
    nb = Notebook(br)
    nb.create_folder()
    nb.open_folder('Untitled Folder')


@then(u'we can list datasets in omegaml')
def step_impl(ctx):
    # test omegaml functionality
    br = ctx.browser
    nb = Notebook(br)
    code = """
    import omegaml as om
    om.datasets.put(['sample'], 'sample', append=False)
    om.datasets.list('sample')
    """.strip()
    nb.new_cell_exec(code)
    sleep(3)
    assert nb.current_cell_output() == "['sample']"

@then(u'we can add a notebook in the folder')
def step_impl(ctx):
    br = ctx.browser
    br.visit(ctx.jynb_url)
    nb = Notebook(br)
    nb.jupyter_home
    nb.open_folder('Untitled Folder')
    nb.create_notebook()
    nb.last_notebook
    assert not br.is_text_present('No such directory')
