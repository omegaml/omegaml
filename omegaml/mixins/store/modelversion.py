from collections import defaultdict

from copy import deepcopy
from hashlib import sha1

# byte string
_u8 = lambda t: t.encode('UTF-8', 'replace') if isinstance(t, str) else t


class ModelVersionMixin(object):
    """
    Versioning support for models

    Usage:
        # create a new version
        om.models.put(model, 'mymodel')

        # get the most recent version
        om.models.get('mymodel', version=-1)

        # tag a model, get specific tag
        om.models.put(model, 'mymodel', tag='foo')
        om.models.get('mymodel', tag='foo')

        # get a specific tag included in name
        om.models.get('mymodel@foo')

        # specify the commit id yourself (e.g. when integrating with git)
        # note this does not interact with git in any way
        om.models.put(model, 'mymodel', commit=<git ref>'

    Notes:
        * every put will create a new version
        * it is not possible to delete a version
        * the versioning is purely based on model Metadata,
          all functionality will continue to work as before
    """

    def put(self, obj, name, tag=None, commit=None, previous='latest', noversion=False, **kwargs):
        if self._model_version_applies(name) and not noversion:
            # create a new version
            base_name, tag, version = self._base_name(name, tag)
            meta = super().put(obj, base_name, **kwargs)
            self._ensure_versioned(meta)
            meta = self._put_version(obj, meta, tag=tag, commit=commit, previous=previous, **kwargs)
        else:
            meta = super().put(obj, name, **kwargs)
        return meta

    def get(self, name, commit=None, tag=None, version=-1, **kwargs):
        if not self._model_version_applies(name):
            return super().get(name, **kwargs)
        meta = self.metadata(name, commit=commit, tag=tag, version=version)
        actual_name = name
        if meta:
            self._ensure_versioned(meta)
            actual_name = self._model_version_actual_name(name, tag=tag,
                                                          commit=commit,
                                                          version=version)
        return super().get(actual_name, **kwargs)

    def drop(self, name, force=False, version=-1, commit=None, tag=None, **kwargs):
        # TODO implement drop to support deletion of specific versions
        if False and self._model_version_applies(name):
            # this messes up the version history of the base object!
            name = self._model_version_actual_name(name, tag=tag, commit=commit, version=version)
        return super().drop(name, force=force, **kwargs)

    def metadata(self, name, bucket=None, prefix=None, version=None, commit=None, tag=None, raw=False, **kwargs):
        if not self._model_version_applies(name):
            return super().metadata(name)
        base_meta, base_commit, base_version = self._base_metadata(name, bucket=bucket, prefix=prefix)
        commit = commit or base_commit
        version = base_version or version or -1
        if raw and base_meta and 'versions' in base_meta.attributes:
            # the actual version's metadata is requested
            actual_name = self._model_version_actual_name(name, tag=tag,
                                                          commit=commit,
                                                          version=version,
                                                          bucket=bucket,
                                                          prefix=prefix)
            meta = super().metadata(actual_name, bucket=bucket, prefix=prefix)
        elif base_meta:
            # there is a versioned entry, return the base
            meta = base_meta
        else:
            # no version found, return the actual object
            meta = super().metadata(name)
        return meta

    def revisions(self, name, raw=False):
        meta = self.metadata(name)
        if meta and self._model_version_applies(name):
            versions = meta.attributes.get('versions', {})
            commits = versions.get('commits', [])
            tags = versions.get('tags', {})
            commit_tags = defaultdict(list)
            for k, v in tags.items():
                commit_tags[v].append(k)
            tagged_revs = [
                f'{name}@{tag}' for tag in tags.keys()
            ]
            non_tagged_revs = [
                f'{name}@{commit["ref"]}' for commit in commits
                if not commit_tags.get(commit['ref'])
            ]
            revisions = tagged_revs + non_tagged_revs
            as_raw = lambda v: [self.metadata(m, raw=True) for m in revisions]
            return as_raw(revisions) if raw else revisions
        return None

    def _versioned_metas(self, name):
        # get all metas that match a given name
        # return list of tuples(actual-meta, actual-name)
        meta = self.metadata(name, raw=True)
        base_meta, *_ = self._base_metadata(name)
        versions = base_meta.attributes.get('versions')
        metas = []
        # if the base version is requested (no @version tag in name)
        # -- update the latest version's metadata with current
        # -- include all tags and versions
        if '@' not in name:
            base_meta.attributes.update(meta.attributes)
            metas.append((base_meta, name))
            # -- add all tagged versions
            for tag in versions['tags']:
                asname = f'{name}@{tag}' if '@' not in name else name
                metas.append((self.metadata(asname, raw=True), asname))
        else:
            # always add the base version's metadata to ensure the version is linked
            metas.append((base_meta, base_meta.name))
            # a specific version is requested, get that
            metas.append((meta, name))
        return metas

    def _base_metadata(self, name, **kwargs):
        name, tag, version = self._base_name(name)
        meta = super().metadata(name, **kwargs)
        return meta, tag, version

    def _base_name(self, name, tag=None, **kwargs):
        # return actual name without version tag
        version = None
        if '^' in str(name):
            version = -1 * (name.count('^') + 1)
            name = name.split('^')[0].split('@')[0]
        elif '@' in str(name):
            name, tag = name.split('@')
        return name, tag, version

    def _model_version_actual_name(self, name, tag=None, commit=None,
                                   version=None, bucket=None, prefix=None):
        meta, name_tag, name_version = self._base_metadata(name, bucket=bucket, prefix=prefix)
        tag = tag or name_tag
        commit = commit or tag
        version = name_version or version or -1
        if meta is not None and 'versions' in meta.attributes:
            actual_name = meta.name
            # we have an existing versioned object
            if tag or commit:
                if tag and tag in meta.attributes['versions']['tags']:
                    version_hash = meta.attributes['versions']['tags'][tag]
                    actual_name = self._model_version_store_key(meta.name, version_hash)
                elif commit:
                    actual_name = self._model_version_store_key(meta.name, commit)
                else:
                    actual_name = name
            else:
                if abs(version) <= len(meta.attributes['versions']['commits']):
                    actual_name = meta.attributes['versions']['commits'][version]['name']
        else:
            actual_name = name
        return actual_name

    def _model_version_hash(self, meta):
        # SEC: CWE-916
        # - status: wontfix
        # - reason: hashcode is used purely for name resolution, not a security function
        hasher = sha1()
        hasher.update(_u8(meta.name))
        hasher.update(_u8(str(meta.modified)))
        return hasher.hexdigest()

    def _model_version_store_key(self, name, version_hash):
        return '_versions/{}/{}'.format(name, version_hash)

    def _model_version_applies(self, name):
        return self.prefix.startswith('models/') and not str(name).startswith('tools/')

    def _ensure_versioned(self, meta):
        if 'versions' not in meta.attributes:
            meta.attributes['versions'] = {}
            meta.attributes['versions']['tags'] = {}
            meta.attributes['versions']['commits'] = []
            meta.attributes['versions']['tree'] = {}

    def _put_version(self, obj, meta, tag=None, commit=None, previous=None, **kwargs):
        version_hash = commit or self._model_version_hash(meta)
        previous = meta.attributes['versions']['tags'].get(previous) or None
        version_name = self._model_version_store_key(meta.name, version_hash)
        version_meta = self.put(obj, version_name, noversion=True, **kwargs)
        version_meta.attributes = deepcopy(meta.attributes)
        version_meta.attributes.update(kwargs.get('attributes', {}))
        if 'versions' in version_meta.attributes:
            del version_meta.attributes['versions']
        version_meta.save()
        meta.attributes['versions']['commits'].append(dict(name=version_meta.name, ref=version_hash))
        meta.attributes['versions']['tree'][version_hash] = previous
        meta.attributes['versions']['tags']['latest'] = version_hash
        if tag:
            meta.attributes['versions']['tags'][tag] = version_hash
        return meta.save()
