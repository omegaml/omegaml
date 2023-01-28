import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from omegaml import settings
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import clear_om


def create_testdata(om):
    reg = LinearRegression()
    df = pd.DataFrame({
        'x': range(1, 100),
    })
    df['y'] = df['x'] * 2 + 1
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
            if i % 2 > 0:
                # simulate multi-level paths
                prefix = f'myapp/{i}/'
            else:
                prefix = ''
            omx.models.put(reg, f'{prefix}{bx}-reg-{i}')
            omx.datasets.put(df, f'{prefix}{bx}-data-{i}', revisions=True)
            omx.scripts.put(myservice, 'hello', replace=True)
            omx.jobs.create(code, f'{prefix}hello')
            omx.jobs.schedule(f'{prefix}hello', 'every Saturday, at 05:00')
            if i < 3:
                omx.runtime.job(f'{prefix}hello').run().get()
            for j in range(10):
                df = df * 0.1 * np.random.randn(*df.shape)
                with omx.runtime.experiment(f'{prefix}{bx}-reg-{i}') as exp:
                    exp.track(f'{prefix}{bx}-reg-{i}')
                    exp.log_metric('acc', .1 + (j * 10 / 100))
                    exp.log_metric('loss', .97 - (j * 10 / 100))
                    if (j % 2) > 0:
                        exp = omx.runtime.experiment(f'{prefix}{bx}-reg-{i}', recreate=True, autotrack=True)
                        mon = exp.as_monitor(f'{prefix}{bx}-reg-{i}')
                        mon.snapshot(X=df[['x']], Y=df[['y']])

        [omx.logger.info(f'{prefix}{bx}-test {i}') for i in range(100)]


if __name__ == '__main__':
    import omegaml as om

    om._base_config.OMEGA_LOCAL_RUNTIME = True
    settings(reload=True)
    om = om.setup()
    clear_om(om)
    create_testdata(om)
