from __future__ import annotations

import json
import re
import tarfile
from bson.json_util import dumps as bson_dumps, loads as bson_loads
from datetime import datetime
from pathlib import Path
from shutil import rmtree

from omegaml.client.util import AttrDict
from omegaml.documents import Metadata
from omegaml.mixins.store.promotion import PromotionMixin
from omegaml.omega import Omega
from omegaml.store import OmegaStore
from omegaml.util import IterableJsonDump, load_class, SystemPosixPath


class ObjectImportExportMixin:
    """ Provide generic import() and export() methods """

    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('data/', 'jobs/', 'models/', 'scripts/', 'streams/')

    def to_archive(self, name, local, fmt='omega', **kwargs):
        backend = self.get_backend(name)
        if hasattr(backend, 'export'):
            return backend.export(name)
        meta = self.metadata(name, raw=True)
        assert meta is not None, f"{name} is not in {self.prefix}"
        if not isinstance(local, OmegaExportArchive):
            archive = OmegaExporter.archive(local, store=self, fmt=fmt)
        else:
            archive = local
        with archive as arc:
            arc.add(meta, asname=name, store=self)
        return arc

    def from_archive(self, local, name, fmt='omega', **kwargs):
        self.drop(name, force=True)
        meta = self._load_metadata(name)
        if not isinstance(local, OmegaExportArchive):
            archive = OmegaExporter.archive(local, store=self, fmt=fmt)
        else:
            archive = local
        with archive as arc:
            meta = arc.extract(name, meta, asname=meta.name, store=self)
        return meta

    def _load_metadata(self, name, attributes=None, gridfile=None):
        meta = self.metadata(name, raw=True)
        return meta or self._make_metadata(
            name=name,
            prefix=self.prefix,
            bucket=self.bucket,
            attributes=attributes,
            gridfile=gridfile)


class OmegaExportArchive:
    def __init__(self, path, store=None):
        self.path = Path(path)
        self.store = store
        self.manifest = self._read_manifest()
        self._with_arc = None

    def __enter__(self, compress=False):
        self._with_arc = arc = self.decompress()
        arc.manifest = arc._read_manifest()
        return arc

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_readonly:
            self.close()

    @property
    def is_readonly(self):
        return self is not self._with_arc

    def _writable(fn):
        def inner(self, *args, **kwargs):
            if not self.is_readonly:
                return fn(self, *args, **kwargs)
            else:
                raise ValueError('archive is not writable')

        return inner

    @_writable
    def clear(self):
        if self.path.exists():
            rmtree(self.path)
        self.manifest = self._read_manifest()

    def compress(self):
        # create a timestamped path that does not contain :
        # -- due to https://superuser.com/a/1720174
        dt = str(datetime.utcnow().isoformat()).replace(':', '')
        tfn = self.path.parent / f'{self.path.name}-{dt}.tgz'
        Path(tfn).unlink(missing_ok=True)
        with tarfile.open(tfn, 'w:gz') as tar:
            tar.add(self.path, arcname=self.path.name, recursive=True)
        self.clear()
        return tfn

    def decompress(self):
        if self.path.is_file():
            target = self.path.parent / self.path.name.replace('.tgz', '')
            with tarfile.open(self.path, 'r:gz') as tar:
                tar.extractall(target)
            # the first entry in the archive is the actual archive contents
            basename = list(target.iterdir())[0]
            arc = self.__class__(basename, self.store)
        else:
            arc = self
        return arc

    @property
    def members(self):
        return self.manifest['members'].keys()

    @_writable
    def add(self, meta, asname=None, store=None):
        store = store or self.store
        name = asname or meta.name
        meta_dict = meta.to_dict()
        # prepare local paths
        lpaths = self._local_paths(self.path, name, store)
        # data in gridfile
        data = meta.gridfile.read()
        if data is not None:
            lpaths.gridfile.write_bytes(data)
            meta_dict['gridfile'] = lpaths.gridfile.name  # basename
        # data in collection
        if meta.collection:
            def remove_id(obj):
                obj.pop('_id', None)
                return obj

            data = store.collection(name).find()
            with lpaths.collection.open('w') as fout:
                IterableJsonDump.dump(data, fout,
                                      transform=remove_id,
                                      default=bson_dumps)
        # metadata
        lpaths.meta.write_text(bson_dumps(meta_dict))
        self.manifest['members'][self._manifest_key(name, store)] = lpaths.key

    @_writable
    def close(self):
        self._write_manifest()

    def extract(self, name, meta, asname=None, store=None):
        store = store or self.store
        lpaths = self._local_paths(self.path, name, store, expect_exist=True)
        with lpaths.meta.open('r') as fin:
            meta_dict = bson_loads(fin.read())
            meta.attributes.update(meta_dict['attributes'])
            meta.kind_meta.update(meta_dict['kind_meta'])
            meta.kind = meta_dict['kind']
        if lpaths.gridfile.exists():
            with lpaths.gridfile.open('rb') as fin:
                file_backend = store.get_backend_byobj(fin)
                meta.gridfile = file_backend._store_to_file(store, fin, lpaths.key)
        if lpaths.collection.exists():
            with lpaths.collection.open('r') as fin:
                data = bson_loads(fin.read())
                collection = store.collection(name)
                collection.insert_many(data)
                meta.collection = collection.name
        if asname:
            meta.name = asname
        return meta.save()

    def _manifest_key(self, name, store):
        return f'{store.prefix}{name}'

    def _local_paths(self, local, name, store, expect_exist=False):
        manifest_key = self._manifest_key(name, store)
        in_manifest = manifest_key in self.manifest['members']
        if not in_manifest and not expect_exist:
            local_key = SystemPosixPath(store.prefix) / store.object_store_key(name, 'omx')
        elif in_manifest:
            local_key = self.manifest['members'][manifest_key]
        else:
            raise ValueError(f'{name} expected to exist, but is not a member in archive {self.path}')
        local_dir = Path(local) / local_key
        local_meta = Path(local_dir) / 'metadata.json'
        local_gridfile = Path(local_dir) / 'gridfile.bin'
        local_collection = Path(local_dir) / 'collection.json'
        local_dir.mkdir(parents=True, exist_ok=True)
        return AttrDict(dir=local_dir,
                        key=str(local_key),
                        meta=local_meta,
                        gridfile=local_gridfile,
                        collection=local_collection)

    def _read_manifest(self):
        manifest_path = self.path / 'manifest.json'
        if manifest_path.exists():
            with manifest_path.open('r') as fin:
                manifest = json.loads(fin.read())
        else:
            manifest = {
                'members': {},
                'format': 'omega',
            }
        return manifest

    def _write_manifest(self):
        self.path.mkdir(exist_ok=True)
        with (self.path / 'manifest.json').open('w') as fout:
            json.dump(self.manifest, fout)


class OmegaExporter:
    ARCHIVERS = {
        'omega': 'omegaml.mixins.store.imexport.OmegaExportArchive',
    }
    _temp_bucket = '__exporter' # used as the import target and source for promotion

    def __init__(self, omega):
        self.omega = omega

    def to_archive(self, path, objects=None, fmt='omega', compress=False, progressfn=None):
        obj: Metadata | str
        store: ObjectImportExportMixin | OmegaStore
        if not objects:
            objects = self.omega.list(raw=True)
        with OmegaExporter.archive(path, fmt=fmt) as arc:
            arc.clear()
            for obj in objects:
                progressfn(obj) if progressfn else None
                if isinstance(obj, Metadata):
                    store = self.omega.store_by_meta(obj)
                    store.to_archive(obj.name, arc)
                elif isinstance(obj, str):
                    try:
                        prefix, pattern = obj.split('/', 1)
                    except ValueError:
                        prefixes = [s.prefix for s in self.omega._stores]
                        raise ValueError(f'Cannot parse {obj}. Specify objects as prefix/name, prefix is one of {prefixes}')
                    store = self.omega.store_by_prefix(f'{prefix}/')
                    # if the pattern does not match in list, use it as a name
                    # e.g. mymodel@version1 will not show in list()
                    objects = store.list(pattern=pattern) or [pattern]
                    for objname in objects:
                        store.to_archive(objname, arc)
        if compress:
            archive_path = arc.compress()
        else:
            archive_path = path
        return archive_path

    def from_archive(self, path, pattern=None, fmt='omega', promote=False,
                     promote_to: Omega=None, progressfn=None):
        # for promotion, use a temp bucket for import and promotion source
        promote = promote or (promote_to is not None)
        promote_to = None if not promote else (promote_to or self.omega)
        omega = self.omega if not promote else promote_to[self._temp_bucket]
        store: ObjectImportExportMixin
        imported = []
        pattern = pattern.replace('datasets/', 'data/') if pattern else pattern
        if not Path(path).exists():
            raise FileNotFoundError(path)
        with OmegaExporter.archive(path, fmt=fmt) as arc:
            for member in arc.members:
                progressfn(member) if progressfn else None
                if pattern and not re.match(pattern, member):
                    continue
                prefix, name = member.split('/', 1)
                store = omega.store_by_prefix(f'{prefix}/')
                meta = store.from_archive(arc, name)
                if promote:
                    store: PromotionMixin
                    to_store = promote_to.store_by_prefix(f'{prefix}/')
                    meta = store.promote(name, to_store)
                imported.append(meta)
        return imported

    @classmethod
    def archive(cls, path, store=None, fmt='omega') -> OmegaExportArchive:
        archiver = load_class(cls.ARCHIVERS[fmt])
        archive = archiver(path, store)
        return archive
