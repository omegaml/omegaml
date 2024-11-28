from flask import url_for
from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView
from omegaml.server.dashboard.views.listdetail import ListDetailMixin


class RepositoryBaseView(ListDetailMixin, BaseView):
    list_template = 'repository/{self.segment}.html'
    detail_template = 'repository/{self.segment}_detail.html'

    @fv.route('/{self.segment}/<path:name>/update', methods=['POST'])
    def api_handle_update(self, name):
        meta = self.store.metadata(name)
        data = self.request.json
        meta.attributes.update(data.get('attributes', {}))
        meta.save()
        return meta.to_json()

    @fv.route('/{self.segment}/<path:name>', methods=['DELETE'])
    def api_handle_delete(self, name):
        if self.store.exists(name):
            self.store.drop(name, force=True)
        return {'redirect_url': (url_for(f'.{self.segment}_view_list'))}
