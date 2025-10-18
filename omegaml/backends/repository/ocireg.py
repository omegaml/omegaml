from pathlib import Path
from urllib.parse import urlparse

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.repository.orasreg import OrasOciRegistry


class OCIRegistryBackend(BaseModelBackend):
    KIND = 'oci.registry'
    PROMOTE = 'metadata'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return str(obj).startswith('oci://') or str(obj.startswith('ocidir://'))

    def put(self, obj, name, **kwargs):
        """ store a reference to an oci registry

        Args:
            obj (str): the uri of the oci registry as oci://hostname:port/namespace/image:tag,
               or ocidir:///path/to/registry/namespace/image:tag
            name (str): the name of the object
            **kwargs: ignored

        Returns:
            meta: Metadata
        """
        meta = self.model_store.metadata(name)
        if meta:
            # save object to registry
            pass
        url = str(obj)
        kind_meta = {
            'url': url,
        }
        attributes = kwargs.get('attributes') or {}
        return self.model_store.make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            kind_meta=kind_meta,
            attributes=attributes).save()

    def get(self, name, image=None, local=None, **kwargs):
        """ retrieve an OCI registry instance

        Args:
            name (str): the name
            image (str): optional, the name of the image specified as image:tag
            local (str): optional, a local path, if specified the image is retrieved
              and extracted to the local path

        Returns:
            OrasOciRegistry: the registry instance
        """
        meta = self.model_store.metadata(name)
        reg = self._get_registry(meta, image=image)
        if local:
            return reg.extract(local, repo=image)
        return reg

    def _get_registry(self, meta, image=None):
        url = meta.kind_meta['url']
        protocol, url, namespace, _image, tag = parse_ociuri(url)
        image = image or _image
        ocidir = protocol == 'ocidir'
        repo = None
        if image:
            image = f'{image}:{tag}' if ':' not in image else image
            repo = f'{namespace}/{image}' if namespace else image
        if ocidir:
            url = Path(url)
            url.mkdir(parents=True, exist_ok=True)
        return OrasOciRegistry(url, repo)


def parse_ociuri(ociuri):
    """ parse OCI URI into components

    Args:
        ociuri (str): string representing an OCI URI or

    Usage:
        protocol, url, namespace, image, tag = parse_ociuri('oci://<url>/<namespace>/<image>:<tag>')
        => (oci, url, namespace, image, tag)
        protocol, url, namespace, image, tag = parse_ociuri('ocidir:///path/<namespace>/<image>:<tag>')
        => (oci, path, namespace, image, tag)

    Returns:
        tuple: protocol, url, namespace, image, tag
    """
    parsed = urlparse(ociuri)
    if parsed.scheme == 'ocidir':
        # ocidir://
        ocidir = Path(parsed.path)
        image, tag = ocidir.name.split(':') if ':' in ocidir.name else ('', 'latest')
        url, namespace = str(ocidir.parent if image else ocidir).rsplit('/', 1)
    else:
        # oci://
        parts = parsed.path.lstrip('/').split('/')
        url = parsed.netloc
        namespace, image = ('/'.join(parts[0:-1]), parts[-1]) if len(parts) > 1 else (parts[0], '')
        image, tag = image.split(':') if ':' in image else (image, 'latest')
    return parsed.scheme, url, namespace, image, tag
