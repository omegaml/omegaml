import pandas as pd
from sklearn.linear_model import LinearRegression

from omegaml import settings
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import clear_om


def create_testdata(om):
    om = om.setup()
    reg = LinearRegression()
    df = pd.DataFrame({
        'a': range(1, 3)
    })
    code = '''
    print("hello world")
    '''
    @virtualobj
    def myservice(*args, **kwargs):
        "hello world"

    for bucket in ('default', 'prod'):
        omx = om[bucket]
        bx = bucket[0]
        for i in range(10):
            omx.models.put(reg, f'{bx}-reg-{i}')
            omx.datasets.put(df, f'{bx}-data-{i}', revisions=True)
            om.scripts.put(myservice, 'hello', replace=True)
            omx.jobs.create(code, 'hello')
            if i == 0:
                omx.runtime.job('hello').run().get()
            with omx.runtime.experiment('test') as exp:
                exp.track(f'{bx}-reg-{i}')
                exp.log_metric('acc', .1 + (i * 10 / 100))
                exp.log_metric('loss', .97 - (i * 10 / 100))
        [omx.logger.info(f'{bx}-test {i}') for i in range(100)]


if __name__ == '__main__':
    import omegaml as om
    om._base_config.OMEGA_LOCAL_RUNTIME = True
    settings(reload=True)
    clear_om(om)
    create_testdata(om)
