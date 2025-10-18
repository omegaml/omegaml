from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.repository import ArtifactRepository
from omegaml.store import OmegaStore


class RepositoryStorageMixin:
    """ Enable
    """

    @classmethod
    def supports(cls, store, **kwargs):
        return True

    def put(self, obj, name, *args, repo=None, **kwargs):
        # if repo= is specified and a valid repo object, use repo as storage
        self: OmegaStore
        meta = self.metadata(name)
        sync = {}
        if meta:
            sync = meta.attributes.get('sync', {})
            repo = repo or sync.get('repo')
        if repo:
            reg: ArtifactRepository = self.get(repo)
            key = self.object_store_key(repo, 'oci')
            # TODO repo_uri / obj_uri come from ArtifactRepository to use its cache
            repo_uri = f'{self.tmppath}/{key}'  # repo files
            obj_uri = f'{self.tmppath}/{key}/{{key}}'  # serialized model
            backend = self.get_backend_byobj(obj)  # type: BaseModelBackend
            target_repo = reg.tag(repo, next=True)  # get next tag (v1, v2, ...)
            reg.add(repo_uri, repo=target_repo)  # add to repo
            meta = backend.put(obj, name, uri=obj_uri)
            sync = meta.attributes.setdefault('sync', sync)
            sync['repo'] = target_repo
        else:
            meta = super().put(obj, name, *args, **kwargs)
        return meta.save()

    def get(self, name, *args, repo=None, **kwargs):
        # if repo= is specified and a valid repo object, use repo as storage
        self: OmegaStore
        meta = self.metadata(name)
        if meta:
            sync = meta.attributes.get('sync', {})
            repo = repo or sync.get('repo')
        if repo:
            reg: ArtifactRepository = self.get(repo)
            # TODO repo_uri / obj_uri come from ArtifactRepository to use its cache
            key = self.object_store_key(repo, 'oci')
            repo_uri = f'{self.tmppath}/{key}'  # repo files
            obj_uri = f'{self.tmppath}/{key}/{{key}}'  # serialized model
            source_repo = reg.tag(repo)  # get latest tag, if not specified
            reg.extract(repo_uri, repo=source_repo)  # pull repo and extract to it
            backend = self.get_backend_byobj(name)  # type: BaseModelBackend
            obj = backend.get(name, uri=obj_uri)
        else:
            obj = super().get(name, *args, **kwargs)
        return obj
