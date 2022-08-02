


def forward(om):
    for meta in om.models.list(raw=True):
        if 'dataset' in meta.attributes and isinstance(meta.attributes.get('dataset'), str):
            meta.attributes.setdefault('tracking', {})
            meta.attributes['tracking']['dataset'] = meta.attributes['dataset']
            del meta.attributes['dataset']
            meta.save()
