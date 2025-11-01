from pathlib import Path
from shutil import rmtree

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.repository.basereg import ArtifactRepository, chdir
from omegaml.store import OmegaStore


class RepositoryStorageMixin:
    """ Enable storing arbitrary serialized objects to OCI artifact repositories

    How it works:
        * models can be stored using om.models.put(), as usualy
        * by default objects (models) are serialized by an object type's backend, packaged and then stored into a gridfile
        * using OCIRegistryBackend, models are serialized the same way, but are stored into an OCI registry instead of gridfile

    Notes:
        * .put('oci://registry:port/namespace', 'reponame') stores the registry url as 'reponame'
        * .get('reponame') returns the ArtifactRepository()
        * .put(obj, name, repo='reponame') uses the obj's backend to create a local file,
          then stores that file to the reponame's ArtifactRepository() instance. The artifact name
          is derived from 'reponame/image:tag', if given, else it uses the object's name to
          yield 'reponame/name:latest'
        * the object's metadata.attributes contain the 'sync' dict with the following format
          'sync': { 'repo': 'reponame', 'image': 'image:tag' }
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
            repo, image = repo.rsplit('/', 1) if '/' in repo else (repo, name)
            reg: ArtifactRepository = self.get(repo, image=image)
            assert reg is not None, f"repository {repo} not found in {self.prefix}"
            key = self.object_store_key(name, 'serialized')
            # create directory to export to
            repo_uri = Path(f'{self.tmppath}/{self.prefix}')  # repo files
            obj_uri = Path(f'{self.tmppath}/{self.prefix}/{key}')  # serialized model
            rmtree(repo_uri, ignore_errors=True)
            obj_uri.parent.mkdir(parents=True, exist_ok=True)
            # serialize obj to a local file, using original backend
            backend = self.get_backend_byobj(obj, **kwargs)  # type: BaseModelBackend
            # target_repo = reg.tag(repo, next=True)  # get next tag (v1, v2, ...)
            meta = backend.put(obj, name, uri=obj_uri)  # uri= stores file to path obj_uri, instead of gridfile
            meta.uri = ''  # uri is only for temporary storage
            sync = meta.attributes.setdefault('sync', sync)
            # store serialized object in repo
            obj_repo_uri = obj_uri.relative_to(obj_uri.parent)
            image, tag = image.split(':') if ':' in image else (image, 'latest')
            target_repo = f'{image}:{tag}'
            sync['repo'] = f'{repo}/{target_repo}'
            with chdir(obj_uri.parent):
                reg.add(obj_repo_uri, repo=target_repo)  # add to repo
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
            repo, image = repo.rsplit('/', 1) if '/' in repo else (repo, name)
            reg: ArtifactRepository = self.get(repo)
            # TODO repo_uri / obj_uri come from ArtifactRepository to use its cache
            key = self.object_store_key(name, 'serialized')
            repo_uri = f'{self.tmppath}/{self.prefix}'  # repo files
            obj_uri = f'{self.tmppath}/{self.prefix}/{key}'  # serialized model
            # source_repo = reg.tag(repo)  # get latest tag, if not specified
            reg.extract(repo_uri, repo=image)  # pull repo and extract to it
            backend = self.get_backend(name, **kwargs)  # type: BaseModelBackend
            obj = backend.get(name, uri=obj_uri)
        else:
            obj = super().get(name, *args, **kwargs)
        return obj
