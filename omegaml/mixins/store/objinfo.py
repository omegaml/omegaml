from omegaml.store import OmegaStore


class ObjectInformationMixin:
    def summary(self, name):
        self : OmegaStore
        meta = self.metadata(name)
        backend = self.get_backend(name)
        contrib = backend.summary(name) if hasattr(backend, 'summary') else {}
        data = {
            'name': name,
            'kind': meta.kind,
            'created': meta.created,
            'modified': meta.modified,
            'docs': meta.attributes.get('docs'),
            'revisions': self.revisions(name) if hasattr(self, 'revisions') else None,
        }
        data.update(contrib)
        return data

