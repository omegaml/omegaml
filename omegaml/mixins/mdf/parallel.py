from joblib import Parallel, delayed

from omegaml.util import PickableCollection


class ParallelApplyMixin:
    """
    Enables parallel apply to MDataFrame

    This enables Python-native Pandas processing to be applied to MDataFrames
    of any size

    Usage:
        def myfunc(df):
            # this function is executed for each chunk in parallel
            # use any Pandas DataFrame native functions
            df[...] = df.apply(...)

        om.datasets.getl('verylarge').transform(myfunc).persist('transformed')
    """

    def transform(self, fn=None, n_jobs=-2, maxobs=None,
                  chunksize=50000, chunkfn=None, outname=None,
                  resolve='worker', backend='omegaml'):
        """

        Args:
            fn (func): the function to apply to each chunk, receives the
               chunk DataFrame (resolve==worker) or MDataFrame (resolve==function)
            n_jobs (int): number of jobs, defaults to CPU count - 1
            maxobs (int): number of max observations to process, defaults to
               len of mdf
            chunksize (int): max size of each chunk, defaults to 50000
            chunkfn (func): the function to chunk by
            outname (name): output collection name, defaults to _tmp_ prefix of
              input name
            resolve (string): worker, function. If worker is specified chunkfn
                receives the resolved DataFrame, otherwise receives the MDataFrame.
                Specify function to apply a custom resolving strategy (e.g. processing
                records one by one). Defaults to worker which uses .value on each
                chunk to resolve each chunk to a DataFrame before sending

        See Also:
            https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html

        Returns:

        """
        mdf = self.__class__(self.collection, **self._getcopy_kwargs())
        options = mdf._transform_options()
        options.update({
            'maxobs': maxobs or len(mdf),
            'n_jobs': n_jobs,
            'chunksize': chunksize,
            'applyfn': fn or pyappply_nop_transform,
            'chunkfn': chunkfn,
            'mdf': mdf,
            'append': False,
            'outname': outname or '_tmp{}_'.format(mdf.collection.name),
            'resolve': resolve,  # worker or function
            'backend': backend,
        })
        return mdf

    def _chunker(self, mdf, chunksize, maxobs):
        if getattr(mdf.collection, 'query', None):
            for i in range(0, maxobs, chunksize):
                yield mdf.skip(i).head(i + chunksize)
        else:
            for i in range(0, maxobs, chunksize):
                yield mdf.iloc[i:i + chunksize]

    def _do_transform(self, verbose=0):
        # setup mdf and parameters
        opts = self._transform_options()
        n_jobs = opts['n_jobs']
        chunksize = opts['chunksize']
        applyfn = opts['applyfn']
        chunkfn = opts['chunkfn'] or self._chunker
        maxobs = opts['maxobs']
        mdf = opts['mdf']
        outname = opts['outname']
        append = opts['append']
        resolve = opts['resolve']
        backend = opts['backend']
        outcoll = PickableCollection(mdf.collection.database[outname])
        if not append:
            outcoll.drop()
        non_transforming = lambda mdf: mdf._clone()
        with Parallel(n_jobs=n_jobs, backend=backend,
                      verbose=verbose) as p:
            # prepare for serialization to remote worker
            chunks = chunkfn(non_transforming(mdf), chunksize, maxobs)
            runner = delayed(pyapply_process_chunk)
            worker_resolves_mdf = resolve in ('worker', 'w')
            # run in parallel
            jobs = [runner(mdf, i, chunksize, applyfn, outcoll, worker_resolves_mdf)
                    for i, mdf in enumerate(chunks)]
            p._backend._job_count = len(jobs)
            if verbose:
                print("Submitting {} tasks".format(len(jobs)))
            p(jobs)
        return outcoll

    def _get_cursor(self, pipeline=None, use_cache=True):
        # called by .value
        if self._transform_options():
            result = self._do_transform().find()
        else:
            result = super()._get_cursor(pipeline=pipeline, use_cache=use_cache)
        return result

    @property
    def is_transforming(self):
        return bool(self._transform_options())

    def _transform_options(self):
        self._pyapply_opts = getattr(self, '_pyapply_opts', {})
        return self._pyapply_opts

    def persist(self, name=None, store=None, append=False, local=False):
        """
        Evaluate and persist the result of a .transform() in chunks

        Args:
            name (str): the name of the target dataset
            store (OmegaStore): the target store, defaults to om.datasets
            append (bool): if True will append the data, otherwise replace. Defaults
               to False
            local (bool): if True resolves a pending aggregation result into memory first, then persists
               result. Defaults to False, effectively persisting the result by the database without
               returning to the local process

        Returns:
            Metadata of persisted dataset
        """
        # -- .transform() active
        options = self._transform_options()
        if options:
            meta = None
            if name and store:
                coll = store.collection(name)
                if coll.name == self.collection.name:
                    raise ValueError('persist() must be to a different collection than already existing')
                try:
                    if not append:
                        store.drop(name, force=True)
                    meta = store.put(coll, name)
                except:
                    print("WARNING please upgrade omegaml to support accessing collections")
                else:
                    # _do_transform expects the collection name, not the store's name
                    name = coll.name
            options.update(dict(outname=name, append=append))
            coll = self._do_transform()
            result = meta or self.__class__(coll, **self._getcopy_kwargs())
        # -- run with noop in parallel
        elif not local and getattr(self, 'apply_fn', None) is None and name:
            # convenience, instead of .value call mdf.persist('name', store=om.datasets)
            result = self.transform().persist(name=name, store=store, append=append)
        # -- some other action is active, e.g. groupby, apply
        elif local or (name and store):
            print("warning: resolving the result of aggregation locally before storing")
            value = self.value
            result = store.put(value, name, append=append)
        else:
            result = super().persist()
        return result


def pyappply_nop_transform(ldf):
    # default transform that does no transformations
    pass


def pyapply_process_chunk(mdf, i, chunksize, applyfn, outcoll, worker_resolves):
    # chunk processor
    import pandas as pd
    from inspect import signature
    # fix pickling issues
    mdf._parser = getattr(mdf, '_parser', None)
    mdf._raw = getattr(mdf, '_raw', None)
    # check apply fn so we can pass the right number of args
    sig = signature(applyfn)
    params = sig.parameters
    try:
        if worker_resolves:
            # requested to resolve value before passing on
            chunkdf = mdf.value
        else:
            # requested to pass on mdf itself
            chunkdf = mdf
    except Exception as e:
        raise e
        raise RuntimeError(f".value on {mdf} cause exception {e})")
    else:
        applyfn_args = [chunkdf, i][0:len(params)]
    # call applyfn
    if len(chunkdf):
        try:
            result = applyfn(*applyfn_args)
        except Exception as e:
            raise RuntimeError(e)
        else:
            chunkdf = result if result is not None else chunkdf
            if isinstance(chunkdf, dict):
                chunkdf = pd.DataFrame(chunkdf)
            if isinstance(chunkdf, pd.Series):
                chunkdf = pd.DataFrame(chunkdf,
                                       index=chunkdf.index,
                                       columns=[str(chunkdf.name)])
        start = i * chunksize
        if chunkdf is not None and len(chunkdf):
            end = start + len(chunkdf)
            chunkdf['_om#rowid'] = pd.RangeIndex(start, end)
            outcoll.insert_many(chunkdf.to_dict(orient='records'))
