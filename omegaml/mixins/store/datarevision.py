# TODO implement drop for revisions!
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from omegaml.util import tryOr


class DataRevisionMixin:
    """ Enable automatically versioned dataframes in om.datasets

    Works by storing a current version of the dataframe with all changes applied
    as the most recent revision. All changes are stored separately in sequence,
    such that any change or previous "as at" version can be retrieved.

    Usage:
        # initial
        om.datasets.put(df, 'mydf', revisions=True)

        # changesets -- will merge mydf by index, and keep track of updates
        om.datasets.put(updates_df, 'mydf')
        om.datasets.put(updates_df, 'mydf', revision_dt=<dt>)
        om.datasets.put(updates_df, 'mydf', tag='tagname')

        # changesets can be used to delete
        # -- delete all by index
        om.datasets.put(updates_df, 'mydf', delete=True)
        # -- delete by specific rows
        updates_df['_delete_'] = True
        om.datasets.put(updates_df, 'mydf')

        # retrieve latest revision, all changes applied
        # -- existing rows are updated by matching the dataframe's index
        # -- new rows are inserted
        # -- deleted rows are removed
        om.datasets.get('mydf')

        # retrieve as at revision
        om.datasets.get('mydf', revision=N|datetime|tag)

        # retrieve changes only
        # -- result contains additional columns, see trace revisions below
        om.datasets.get('mydf', changeset=N)

        # trace revisions - similar to changeset, but apply all revisions
        # -- result contains additional columns
        #    - _om#revision - the sequence this row was last applied from
        #    - _delete_ - the delete flag, if True row was deleted in change set (note the
        #                 deletion is _not_ applied upon trace_revisions=True)
        om.datasets.get('mydf', trace_revisions=True)

    Metadata:
        meta.kind_meta['revisions'] = {
            'seq': N, # the most recent revision sequence, starting at 0
            'name': '.revisions.dataset', #the name of the revision dataset
            'changes': [{
               'dt': <timestamp>, # the creation timestamp of the change
               'seq': N, # the sequence of the revision
               'tags': [], # list of tags to identify this revision
            }, ...]
        }

    Notes:
        * this is currently implemented for pd.DataFrames only, however the mixin
          uses a revision protocol that is independent of the underlying storage
        * to implement revision support for another storage, override the _make_upsert_fn,
          _get_revisions, _apply_changeset methods. In a minimal implementation, _make_upsert_fn
          is the only method required as all other methods leverage the OmegaStore semantics.

    """

    @classmethod
    def supports(cls, store):
        return store.prefix == 'data/'

    def _has_revisions(self, name, revisions=False):
        # return True if revisions exist for dataset name, or if requested
        meta = self.metadata(name)
        revisions = revisions or (meta is not None and 'revisions' in meta.kind_meta)
        return revisions

    def _build_revision(self, df, name, append=True, revision_dt=None, tag=None, delete=False, **kwargs):
        """ build a new revision

        Creates and updates a 'revisions' entry in the datasets meta.kind_meta, keeping
        track of all changes:

        meta.kind_meta['revisions'] = {
           'seq': N, # the most recent revision, 0-indexed
           'name': revname # the name of the revision collection
           'changes': [{
              'dt': <datetime>,
              'seq': N,
              'tags': [str, ...],
              'delete': True|False,
           }, ...]
        }
        """
        # build a new revision
        # -- set revision dataset
        revname = '.revisions.{name}'.format(**locals())
        # -- deal with replacement, dropping dataset and all revisions
        if not append:
            super().drop(name, force=True)
            super().drop(revname, force=True)
        # build revision metadata
        if '_delete_' not in df.columns:
            df['_delete_'] = delete
        meta = self.metadata(name)
        if meta is not None:
            # _calculate and record revision
            revision = meta.kind_meta['revisions'].get('seq', 0) + 1
            df['_om#revision'] = revision
        else:
            revision = 0
            df['_om#revision'] = revision
            meta = super().put(df, name, append=False, **kwargs)
        revisions = meta.kind_meta.setdefault('revisions', {})
        changesets = revisions.setdefault('changes', [])
        revisions.update({
            'seq': revision,
            'name': revname
        })
        changesets.append({
            'dt': revision_dt or datetime.utcnow(),
            'seq': revision,
            'tags': [tag] if tag else [],
            'delete': delete,
        })
        meta.save()
        # -- record all changes to revision dataset
        self._store_changeset(df, revname, append=append)
        return meta

    def _store_changeset(self, df, revname, append=True, **kwargs):
        return super().put(df, revname, append=append)

    def _retrieve_revision(self, name, revision=-1, changeset=None, trace_revisions=False, **kwargs):
        # retrieve a revision or a specific changeset
        # -- determine revision to get
        meta = self.metadata(name)
        revname = meta.kind_meta['revisions']['name']
        latest_revision = meta.kind_meta['revisions']['seq']
        changes = meta.kind_meta['revisions']['changes']
        # -- return changeset if requested
        if changeset is not None:
            data = super().get(revname, filter={'_om#revision': changeset}, **kwargs)
            return self._clean(data, trace_revisions=trace_revisions)
        if isinstance(revision, int):
            # get revision by sequence
            revision = revision if revision is not None else latest_revision
            revision = min(revision, latest_revision)
            if revision < -1:
                revision = changes[revision]['seq']
        elif isinstance(revision, datetime):
            # get revision by nearest date ("as before or latest at")
            requested = revision
            revision = changes[0]['seq']  # earliest revision by default
            for cs in changes:
                if cs['dt'] > requested:
                    break
                revision = cs['seq']
            else:
                # we did find any before or at, return latest
                revision = latest_revision
        else:
            # get revision by tag
            changes = meta.kind_meta['revisions']['changes']
            requested = revision
            for cs in changes:
                if requested in cs['tags']:
                    revision = cs['seq']
                    break
            else:
                return None
        # -- latest revision is simply the current dataset
        if not trace_revisions and (revision == -1 or revision == latest_revision):
            data = super().get(name, **kwargs)
        else:
            # -- get all changesets up to requested revision
            data = self._apply_changesets(revname, revision, trace_revisions=trace_revisions, **kwargs)
        self._clean(data, trace_revisions=trace_revisions)
        return data

    def _apply_changesets(self, revname, revision, trace_revisions=False, **kwargs):
        # get base revision and apply all changesets up to requested by merging in sequence
        # -- merge
        base = super().get(revname, filter={'_om#revision': 0}, **kwargs)
        base_types = base.dtypes
        idx_type = base.index.dtype
        for rev in range(1, revision + 1):
            changes = super().get(revname, filter={'_om#revision': rev}, **kwargs)
            if changes is None:
                continue
            # apply upserts, step 1
            base = base.merge(changes,
                              how='outer',
                              left_index=True,
                              right_index=True,
                              suffixes=(None, '_r_'))
            # apply upserts, step 2
            revcols = []
            for col in [c for c in base.columns if not c.endswith('_r_')]:
                revcol = col + '_r_'
                base[col] = base[revcol].fillna(base[col]).astype(base_types[col])
                revcols.append(revcol)
            base.index = base.index.astype(idx_type)
            if revcols:
                base.drop(columns=revcols, inplace=True)
            # apply deletions
            if not trace_revisions:
                flt_delete = base['_delete_'] == True  # noqa
                base = base[~flt_delete]
        return base

    def _make_upsert_fn(self, name, delete=False):
        collection = self.collection(name)

        def upsert(obj, store, name, chunksize=1):  # noqa
            from pymongo import DeleteOne, UpdateOne

            ops_updates = []
            ops_deletions = []

            for i, row in tqdm(obj.iterrows(), total=len(obj)):
                data = row.to_dict()
                # om rowid is re-added on insert only to preserve existing row id
                del data['_om#rowid']
                updates = {
                    '$set': data,
                    '$setOnInsert': {
                        '_om#rowid': row['_om#rowid']
                    }
                }
                key = {k: v for k, v in data.items() if k.startswith('_idx#')}
                if data.get('_delete_', delete):
                    # collection.delete_one(key)
                    ops_deletions.append(DeleteOne(key))
                else:
                    # collection.update_one(key, updates, upsert=True)
                    ops_updates.append(UpdateOne(key, updates, upsert=True))

            # do all updates in one step
            collection.bulk_write(ops_deletions + ops_updates)

        return upsert

    def _clean(self, df, trace_revisions=False):
        if not trace_revisions:
            df.drop(columns=['_om#revision', '_delete_'], inplace=True)
        return df

    def put(self, df, name, revisions=False, tag=None, revision_dt=None, trace_revisions=False, **kwargs):
        """ store a dataset revision

        Args:
            df (pd.DataFrame): a dataframe
            name (str): name of dataset
            append (bool): whether to append or replace the dataset, by default append, defaults to True
            delete (bool): whether to upsert changes or to delete by index, defaults to False i.e. upsert
            revisions (bool): if True, keep revisions. defaults to False
            revision_dt (datetime): if specified set this as the revision datetime
            tag (str): optional, if specified record this revision given the tag
            trace_revisions (bool): optional, if True return information on applied revisions (deletions
              are flagged as the _delete_ flag, not applied)
        """
        if not self._has_revisions(name, revisions=revisions):
            return super().put(df, name, **kwargs)
        # revisions apply
        append = kwargs.pop('append', True)
        delete = kwargs.pop('delete', False)
        meta = self._build_revision(df, name, append=append, tag=tag, delete=delete,
                                    revision_dt=revision_dt, **kwargs)
        if append:
            # _fast_insert is a callback to process the upserts
            super().put(df, name, _fast_insert=self._make_upsert_fn(name, delete=delete))
        self._clean(df, trace_revisions=trace_revisions)
        return meta

    def get(self, name, revision=-1, changeset=None, trace_revisions=False, **kwargs):
        """ retrieve a dataset with revisions

        Retrieve a specific revision, including all changes applied until that point. If
        revision is -1 (latest), the current dataset is returned. For any other revision,
        all changes up to this point are applied by merging the first revision with all
        later changes. If a changeset is requested only this changeset is returned. Revisions
        can be specified as a zero-indexed sequence number.

        Args:
            name (str): dataset name
            revision (int|datetime|str): optional, 0-indexed revision sequence (0=first) or -1 negative index
              since last change (-1 = latest), or previous and up to changes before datetime, or
              a tag name. Defaults to -1, returning the latest version of the data
            changeset: optional, if given, specifies the 0-indexed changeset sequence, if specified
              changeset is returned
            trace_revisions (bool): optional, if True return information on applied revisions (deletions
              are flagged as the _delete_ flag, not applied)
        """
        # we pass revisions=None to enforce decision by meta data
        if not self._has_revisions(name, revisions=None):
            return super().get(name, **kwargs)
        # check if revision is a datetime value
        if isinstance(revision, str):
            revision = tryOr(lambda: pd.to_datetime(revision).to_pydatetime(), revision)
        data = self._retrieve_revision(name,
                                       revision=revision,
                                       changeset=changeset,
                                       trace_revisions=trace_revisions,
                                       **kwargs)
        return data

    def revisions(self, name):
        meta = self.metadata(name)
        changes = meta.kind_meta['revisions']['changes']
        return pd.DataFrame(changes)
