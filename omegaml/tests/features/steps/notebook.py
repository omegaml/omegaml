from behave import when, then
from time import sleep

from omegaml.tests.features.util import Notebook, jburl


@when(u'we open jupyter')
def open_jupyter(ctx):
    br = ctx.browser
    br.visit(jburl(ctx.feature.jynb_url, ''))
    nb = Notebook(br, password='omegamlisfun')
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


@when(u'we restart the notebook')
def restart_kernel(ctx):
    br = ctx.browser
    nb = Notebook(br)
    nb.restart(wait=True)


@when(u'we create a folder')
def create_folder(ctx):
    br = ctx.browser
    nb = Notebook(br)
    nb.jupyter_home
    nb.create_folder()
    nb.open_folder('Untitled Folder')


@then(u'we can list datasets in omegaml')
def list_datasets(ctx):
    # test omegaml functionality
    br = ctx.browser
    nb = Notebook(br)
    nb.last_notebook
    code = """
    import omegaml as om
    om.datasets.put(['sample'], 'sample', append=False)
    om.datasets.list('sample')
    """.strip()
    nb.new_cell_exec(code)
    sleep(10)
    current = nb.current_cell_output()
    expected = "['sample']"
    assert expected in current, "Expected {expected}, got {current}".format(**locals())


@then(u'we can add a notebook in the folder')
def add_notebook_in_folder(ctx):
    br = ctx.browser
    br.visit(jburl(ctx.feature.jynb_url, '', nbstyle='tree'))
    nb = Notebook(br)
    nb.jupyter_home
    nb.open_folder('Untitled Folder')
    nb.create_notebook()
    nb.last_notebook
    assert not br.is_text_present('No such directory')
