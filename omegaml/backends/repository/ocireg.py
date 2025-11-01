from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.repository.orasreg import OrasOciRegistry


class OCIRegistryBackend(BaseModelBackend):
    """ enable storing references to OCI repositories

    Concepts:
        * Registry - the name of the service hosting OCI artifacts, e.g. https://ghcr.io
        * Repository - the name of the image or artifact (image is a type of artifact), e.g. https://ghcr.io/namespace
        * Artifact - the name of the object containing files/data as binary blobs, e.g. the name part in https://ghcr.io/namespace/name
        * Artifact:Tag - the specific version of the artifact, e.g. the name:tag part in https://ghcr.io/namespace/name:tag
        * Layers -  a list of blobs making up an artifact, not directly adressable, part of the artifact's Manifest
        * Blob - data payload of an artifact, typically in .tgz or octet(binary) format, directly adresseable by a digest
        * Digest - typically the sha256 of a blob's data
        * Manifest - the metadata attached to an artifact
        * Config - optional config data attached to an artifact

        In short, a registry is a type of fileserver, an artifact is a data structure that contains metadata (Manifest)
        and data (Blob). To enable storing arbitrary data of arbitrary size, and to enable efficient storage, each artifact
        can reference multiple blobs. The registry stores the blobs independent of the artifact, that is multiple artifacts
        can reference the same blob, since the layers don't actually contain data but references (by digest) to the blobs.
    """
    KIND = 'oci.registry'
    PROMOTE = 'metadata'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return str(obj).startswith('oci://') or str(obj).startswith('ocidir://')

    def put(self, obj, name, asname=None, **kwargs):
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
            assert asname is not None, "require asname=<object name> to store in OCI repository"
            return self.model_store.put(obj, asname, repo=name)
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
        # TODO resolve placeholders
        url = meta.kind_meta['url']
        return OrasOciRegistry(url, repo=image)
