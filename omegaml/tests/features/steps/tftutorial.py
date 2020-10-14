import os

from behave import when, then

from omegaml.tests.features.util import Notebook, jburl


@when('we upload the {nbname} notebook')
def uploadtutorial(ctx, nbname):
    # uploading does not work because a native dialogue is opened
    # br.find_by_css('input.fileinput')
    # br.find_by_css('input.fileinput').click() # opens a native file dialoge
    from nbformat import read as nbread
    br = ctx.browser
    om = ctx.feature.om
    # upload directly
    nbfname = os.path.join(ctx.nbfiles, '{nbname}.ipynb'.format(**locals()))
    nbcells = nbread(nbfname, as_version=4)
    om.jobs.put(nbcells, nbname)
    # now run the notebook
    userid = getattr(om.runtime.auth, 'userid', '')
    br.visit(jburl(ctx.feature.jynb_url, userid, nbstyle='tree'))
    assert br.is_text_present(nbname, wait_time=30)


@when('we run the notebook {nbname}')
def runnotebook(ctx, nbname):
    br = ctx.browser
    om = ctx.feature.om
    userid = getattr(om.runtime.auth, 'userid', '')
    br.visit(jburl(ctx.feature.jynb_url, userid, nbstyle='tree'))
    nb = Notebook(br)
    # FIXME sometimes it takes long for the nb to appear. why?
    nb.open_notebook(nbname, retry=10)
    nb.run_all_cells(wait=True)
    nb.save_notebook()
    assert not br.is_text_present('Error')
    assert not br.is_text_present('Exception')
    assert not br.is_text_present('failed')
    assert not br.is_text_present('MissingSchema')
    assert not br.is_text_present('error')


@then('model {model_name} exists')
def checkmodel(ctx, model_name):
    br = ctx.browser
    om = ctx.feature.om
    assert model_name in om.models.list()

@then('dataset {dataset_name} exists')
def checkdataset(ctx, dataset_name):
    br = ctx.browser
    om = ctx.feature.om
    assert dataset_name in om.datasets.list()
