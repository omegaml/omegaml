from time import sleep

from behave import when, then

from omegaml.tests.features.util import Notebook


@when(u'we open jupyter')
def open_jupyter(ctx):
    br = ctx.browser
    br.visit(ctx.feature.jynb_url)
    nb = Notebook(br)
    login_required = br.is_text_present('Password', wait_time=2)
    login_required |= br.is_text_present('token', wait_time=2)
    if login_required:
        nb.login()
    nb.jupyter_home


@when(u'we create a notebook')
def create_notebook(ctx):
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
def list_datasets(ctx):
    # test omegaml functionality
    br = ctx.browser
    nb = Notebook(br)
    code = """
    import omegaml as om
    om.datasets.put(['sample'], 'sample', append=False)
    om.datasets.list('sample')
    """.strip()
    nb.new_cell_exec(code)
    sleep(10)
    current = nb.current_cell_output()
    expected = "['sample']"
    assert current == expected, "Expected {expected}, got {current}".format(**locals)


@then(u'we can add a notebook in the folder')
def add_notebook_in_folder(ctx):
    br = ctx.browser
    br.visit(ctx.feature.jynb_url)
    nb = Notebook(br)
    nb.jupyter_home
    nb.open_folder('Untitled Folder')
    nb.create_notebook()
    nb.last_notebook
    assert not br.is_text_present('No such directory')
