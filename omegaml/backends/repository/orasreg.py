import json
import os
import shutil
import tarfile
from pathlib import Path
from uuid import uuid4

from omegaml.backends.repository import ArtifactRepository, c, f
from omegaml.util import tryOr


class OrasOciRegistry(ArtifactRepository):
    """ArtifactRepository implementation backed by an OCI registry accessed via oras.

    Args:
        url (str|Path): Base URL or local path to the OCI registry.
        repo (str, optional): Repository name including tag (e.g. 'myrepo:tag').

    Usage:

    """

    def __init__(self, url, repo=None):
        super().__init__(url, repo=repo)
        cachedir = repo.replace(":", "-") if repo else uuid4().hex
        self.cache = Path('/tmp') / '.oras' / cachedir
        os.environ.setdefault('ORAS_CACHE', str(self.cache))
        if repo:
            assert ':' in repo, "must specify a :tag"

    def logging(self):
        """ this """
        print()

    def __repr__(self):
        """Return a short representation showing the registry URL and repo."""
        return f'OCIRegistry({self.url}/{self.repo})'

    def login(self, user, token):
        """Log in to the registry using oras.

        This calls `oras login <url> -u <user> --password <token>`.
        """
        cmd = f"oras login {self.url} -u {user} --password {token}"
        c(cmd)  # subprocess.run wrapper, no output expected

    def ocidir(self, opt='--oci-layout'):
        """Return the CLI option for local OCI layout if the URL is a path.

        Args:
            opt (str): Option string to return when URL points to a filesystem path.

        Returns:
            str: opt if the url exists as a filesystem path, otherwise empty string.
        """
        return opt if Path(self.url).exists() else ''

    def create(self, repo=None, exists_ok=False):
        """Create an (empty) repository on the registry.

        Uses `oras push` with an empty config to initialize the repo.

        Args:
            repo (str, optional): Repo name to create. Defaults to self.repo.
            exists_ok (bool): If False, raise an error when the repo already exists.

        Returns:
            dict: Parsed JSON output from oras describing the pushed manifest.
        """
        repo = repo or self.repo
        exists = tryOr(lambda: len(self.tags(repo)) > 0, False)
        if not exists_ok and exists:
            raise ValueError(f'{self.url}/{repo} already exists')
        self._validate('repo', **x(locals()))
        output = c((f'oras push {self.ocidir()} {self.url}/{repo} '
                    f'--config /dev/null:application/vnd.oci.image.config.v1+json --format json'))
        return output | f(json.loads)

    def add(self, paths, repo=None, types=None):
        """Add files to the repository with optional media types.

        Args:
            paths (str|Path|list): Path or list of paths to push.
            repo (str, optional): Repo to push to. Defaults to self.repo.
            types (list, optional): Media types corresponding to paths. If an
                entry is empty, ORAS default type will be used.

        Returns:
            dict: Parsed JSON output from oras describing the push.
        """
        repo_path = repo if repo else self.repo
        self._validate('repo', **x(locals()))
        types = types or []
        if not isinstance(paths, (tuple, list)):
            paths = [paths]
        types = types + [''] * len(paths)  # ensure every path has a corresponding type entry
        types = types[:len(paths)]
        for i, t in enumerate(types):
            p = Path(paths[i])
            if not p.is_dir():
                t = self._guess_type(p)
            paths[i] = f'{paths[i]}:{t}' if t else paths[i]
        path = ' '.join(paths)
        cmd = f"oras push {self.ocidir()} {self.url}/{repo_path} {path} --format json"
        output = c(cmd)  # No output expected
        return output | f(json.loads)

    def delete(self, repo=None, digest=None, force=False):
        """Delete a repo or a specific blob from the registry.

        If digest is omitted, deletes all blobs and the manifest for the repo.
        If digest is provided, deletes only that blob.

        Args:
            repo (str, optional): Repo to delete from. Defaults to self.repo.
            digest (str, optional): Specific blob digest to delete.
            force (bool, optional): if True ignores errors
        """
        repo = repo or self.repo
        exists = tryOr(lambda: len(self.tags(repo)) > 0, False)
        self._validate('repo', **x(locals()))
        drepo = repo.split(':')[0]
        if exists:
            if not digest:
                self._validate('url', 'repo', **x(locals()))
                for artifact in self.artifacts(repo=repo):
                    digest = artifact['digest']
                    cmd = f'oras blob delete --force {self.ocidir()} {self.url}/{drepo}@{digest}'
                    c(cmd)

                cmd = f'oras manifest delete --force {self.ocidir()} {self.url}/{repo}'
                c(cmd)
            else:
                cmd = f'oras blob delete --force {self.ocidir()} {self.url}/{drepo}@{digest}'
                c(cmd)
        elif not force:
            raise ValueError(f'{repo} does not exist (no tags)')

    def extract(self, path, digest=None, repo=None, keep_blobs=False):
        """Extract files from the repository into a local directory.

        If blobs are tar archives they will be extracted. For non-tar blobs the
        original filename is inferred from the OCI annotations and preserved.

        Args:
            path (str|Path): Local directory to extract into.
            digest (str, optional): Ignored (kept for compatibility).
            repo (str, optional): Repo to extract from. Defaults to self.repo.
            keep_blobs (bool): If True, keep downloaded blob files under <path>/blobs.

        Returns:
            list: Local filenames (Path objects) of downloaded blobs.
        """
        # TODO for the whole repo, we can just use oras pull -- it will download and extract automatically
        #      for specific digest, we can use oras blob fetch -- because oras pull runs into file size limits
        #      (for digests). that is, we don't need to go one by one, or unpack gzips ourselves
        #      (although this may be more failsafe/controllable
        # use repo without tag when pulling blobs
        repo_path = repo if repo else self.repo
        repo_path = repo_path.split(':')[0]
        lpath = Path(path)
        lpath.mkdir(parents=True, exist_ok=True)
        artifacts = self.artifacts(repo)
        filenames = []
        for a in artifacts:
            digest = a['digest']
            mediatype = a['mediaType']
            # prepare to extract tar blobs
            if '.tar' in mediatype:
                filename = lpath / 'blobs'
                filename.mkdir(exist_ok=True)
                filename = filename / digest.split(':')[-1]
                is_tar = True
                is_gzip = 'zip' in mediatype
            else:
                # keep plain files as is; infer filename from OCI annotation title
                is_tar = False
                is_gzip = False
                filename = lpath / Path(a.get('annotations', {}).get('org.opencontainers.image.title')).name
            cmd = f"oras blob fetch {self.ocidir()} -o {filename} {self.url}/{repo_path}@{digest}"
            c(cmd)
            if is_tar:
                # extract tar blobs into destination directory
                mode = 'r:gz' if is_gzip else 'r'
                with tarfile.open(filename, mode=mode) as tar:
                    tar.extractall(lpath)
            filenames.append(filename)
        if not keep_blobs:
            shutil.rmtree(lpath / 'blobs', ignore_errors=True)
        return filenames

    def manifest(self, repo=None):
        """Fetch and return the manifest JSON for the given repo.

        Args:
            repo (str, optional): Repo to fetch. Defaults to self.repo.

        Returns:
            dict: Parsed manifest JSON.
        """
        repo = repo or self.repo
        self._validate('repo', **x(locals()))
        cmd = f"oras manifest fetch {self.ocidir()} {self.url}/{repo}"
        output = c(cmd) | f(json.loads)
        return output

    def artifacts(self, filter=None, repo=None):
        """Return the list of artifact layers described in the manifest.

        Args:
            filter: Ignored (kept for API compatibility).
            repo (str, optional): Repo to inspect. Defaults to self.repo.

        Returns:
            list: List of layer dictionaries from the manifest.
        """
        repo = repo or self.repo
        self._validate('repo', **x(locals()))
        manifest = self.manifest(repo=repo)
        return manifest['layers']

    def tags(self, repo=None):
        """List tags for the given repository name (without tag suffix).

        Args:
            repo (str, optional): Repo to query. Defaults to self.repo.

        Returns:
            list: Tags present in the repository.
        """
        repo = repo or self.repo
        repo = repo.split(':')[0]
        self._validate('repo', **x(locals()))
        cmd = f'oras repo tags {self.ocidir()} {self.url}/{repo} --format json'
        output = c(cmd) | f(json.loads)
        return output['tags']

    def artifact(self, digest, repo=None):
        """Return the raw manifest for a specific digest.

        Args:
            digest (str): Digest identifying the artifact.
            repo (str, optional): Repo containing the digest. Defaults to self.repo.

        Returns:
            str: The manifest text for the digest.
        """
        repo_path = repo if repo else self.repo
        self._validate('repo', **x(locals()))
        cmd = f"oras manifest fetch {self.url}/{repo_path}@{digest}"
        output = c(cmd).decode('utf-8')
        return output

    @property
    def members(self):
        """List member blob digests for the current repo."""
        repo = self.repo
        self._validate('repo', **x(locals()))
        artifacts = self.artifacts(repo)
        return [m['digest'] for m in artifacts]

    def _guess_type(self, p):
        """Return a reasonable media type for a file path based on extension.

        Args:
            p (str|Path): File path.

        Returns:
            str: Media type string (defaults to application/octet-stream).
        """
        COMMON_TYPES = {
            '.json': 'application/json',
            '.yaml': 'application/yaml',
            '.yml': 'application/yaml',
            '.txt': 'text/plain',
            '.rst': 'text/plain',
            '.md': 'text/markdown',
            '.js': 'text/javascript',
            '.html': 'text/html',
            '.tar': 'application/vnd.oci.image.layer.v1.tar',
            '.tgz': 'application/vnd.oci.image.layer.v1.tar+gzip',
            '.bin': 'application/octet-stream',
        }
        return COMMON_TYPES.get(Path(p).suffix) or COMMON_TYPES.get('.bin')  # default to binary

    def _validate(self, *ops, repo=None, url=None, **kwargs):
        # validate current settings before operation is called
        repo = repo or self.repo
        url = url or self.url
        CHECKS = {
            'repo': lambda: (repo is not None, "no repository (image), specify repo='name:tag'"),
            'url': lambda: (url is not None, "no registry (url or ocidir), specify OCIOrasRegistry(url|path)")
        }
        OPERATIONS = {
            'push': ['repo'],
        }
        checks_as_ops = {
            k: [k] for k, v in CHECKS.items()
        }
        OPERATIONS.update(**checks_as_ops)
        for op in ops:
            for check in OPERATIONS[op]:
                valid, message = CHECKS[check]()
                assert valid, f"{message}: {op}"


def x(kwargs):
    kwargs.pop('self', None)
    return kwargs


if __name__ == '__main__':
    reg = OrasOciRegistry('.', 'orasimage:test')
    reg.artifacts()
