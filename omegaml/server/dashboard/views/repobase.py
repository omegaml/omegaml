from flask import render_template

from omegaml.server.dashboard.views.base import BaseView
from omegaml.server import flaskview as fv


class RepositoryBaseView(BaseView):
    list_template = 'repository/{self.segment}.html'
    detail_template = 'repository/{self.segment}_detail.html'

    @fv.route('/{self.segment}')
    def view_list(self, template=None):
        template = template or self.list_template.format(self=self)
        items = self.members()
        return render_template(f"dashboard/{template}",
                               segment=self.segment,
                               items=items,
                               buckets=self.buckets)

    @fv.route('/{self.segment}/<path:name>')
    def view_detail(self, name, template=None):
        template = template or self.detail_template.format(self=self)
        meta = self.store.metadata(name)
        data = {
            'meta': meta.to_dict(),
            'summary': self.store.summary(name),
        }
        data.update(self.detail_data(name, data=data, meta=meta))
        return render_template(f"dashboard/{template}",
                               segment=self.segment,
                               buckets=self.buckets,
                               **data)

    def detail_data(self, name, data=None, meta=None):
        return {}

    @fv.route('/{self.segment}/<path:name>/update', methods=['POST'])
    def api_handle_update(self, name):
        meta = self.store.metadata(name)
        data = self.request.json
        meta.attributes.update(data.get('attributes', {}))
        meta.save()
        return meta.to_json()
