from joblib import Parallel, delayed
from sqlalchemy.exc import OperationalError

from omegaml.util import ProcessLocal


class ParallelStep(object):
    def __init__(self, steps=None, agg=None, n_jobs=-1):
        self.steps = steps
        self.agg = agg or self._default_agg
        self.n_jobs = n_jobs

    def aggregate(self, values, **kwargs):
        return self.agg(values, **kwargs)

    def _default_agg(self, values, **kwargs):
        return list(values)

    def __call__(self, value, **kwargs):
        values = Parallel(n_jobs=self.n_jobs)(delayed(pfn)(value, **kwargs) for pfn in self.steps)
        return self.aggregate(values, **kwargs)


class DataPipeline(object):
    """ A data pipeline that processes data through a series of steps

    The pipeline is a sequence of steps, each of which is a callable that
    processes the data.

    .. versionchanged:: 0.17
        The pipeline now automatically gets a context object that is passed
        along to each step as a keyword argument.
    """
    def __init__(self, steps, *args, context=None, n_jobs=None, **kwargs):
        self.steps = steps
        self.args = args
        self.kwargs = kwargs
        self.context = context or ProcessLocal()
        self.n_jobs = n_jobs or -1

    def set_params(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    def process(self, value=None, **kwargs):
        for stepfn in self.steps:
            value = stepfn(value, context=self.context, **kwargs)
        return value

    def __call__(self, value=None, **kwargs):
        return self.process(value, **kwargs)

    def map(self, values, **kwargs):
        parallel_steps = self.steps[:-1] if len(self.steps) > 1 else self.steps
        finalizer = self.steps[-1] if len(self.steps) > 1 else lambda values, **kwargs: values
        pfn = DataPipeline(*self.args, steps=parallel_steps, context=self.context, **self.kwargs)
        parallel = Parallel(n_jobs=self.n_jobs)
        results = parallel(delayed(pfn)(**kwargs) for kwargs in values)
        return finalizer(results, context=self.context, **kwargs)


class Model:
    dburl = 'sqlite:///:memory:'
    name = ''
    sql = 'select * from :sqltable'
    table = None
    chunksize = None
    delete_sql = 'delete from :sqltable'
    keys = None
    join_sql = '''
    with join_:sqltable as (
       select {{_join_vars_a}}, {{_join_vars_b}}
       from   :sqltable as a
       join  {{_join_sqltable}} as b
       on    1 = 1 {{_join_cond}}   
    )

    select *
    from join_:sqltable
    '''

    def __init__(self, sql=None, om=None):
        self.sql = sql or self.sql
        self._om = om
        self.setup()

    @property
    def om(self):
        import omegaml as _baseom
        self._om = self._om or _baseom
        return self._om

    @property
    def store(self):
        return self.om.datasets

    def setup(self):
        assert self.name, 'name must be set'
        return self.store.put(self.dburl, self.name, sql=self.sql, table=self.table)

    def query(self, *args, sql=None, chunksize=None, trusted=False, **vars):
        chunksize = chunksize or self.chunksize
        return self.store.get(self.name, chunksize=chunksize, sqlvars=vars, sql=sql, trusted=trusted)

    def insert(self, data):
        return self.store.put(data, self.name, index=False)

    def transform(self, value, **kwargs):
        return value

    def delete(self, *args, sql=None, **kwargs):
        sql = sql or self.delete_sql
        try:
            cursor = self.store.get(self.name, sql=sql, sqlvars=kwargs, lazy=True)
        except OperationalError as e:
            pass
        else:
            cursor.close()

    def drop(self, force=False):
        return self.store.drop(self.name, force=force)

    def join(self, other, on=None, on_left=None, on_right=None, columns_left=None, columns_right=None, **kwargs):
        join_sql = self.join_sql
        join_keys = {
            ka: kb for ka, kb in zip(on or on_left or [], on or on_right or [])
        }
        _join_cond = ' and '.join([f'a.{k} = b.{v}' for k, v in join_keys.items()])
        _join_cond = ' and ' + _join_cond if _join_cond else ''
        _left_cols = ','.join(columns_left or ['a.*'])
        _right_cols = ','.join(columns_right or ['b.*'])
        sqlvars = {
            '_join_vars_a': _left_cols,
            '_join_vars_b': _right_cols,
            '_join_sqltable': self.store.get_backend(self.name)._default_table(other.table or other.name),
            '_join_cond': _join_cond,
        }
        return self.query(sql=join_sql, trusted=self.store.get_backend(self.name).sign(sqlvars), **sqlvars)

    def count(self, sql=None, raw=False, **vars):
        if raw and not vars:
            sql = sql or 'select count(*) from :sqltable'
            count = self.query(sql=sql).values[-1]
        else:
            count = len(self.query(sql=sql, **vars))
        return count

    def __call__(self, value, **kwargs):
        value = self.query(**kwargs)
        return self.transform(value, **kwargs)
