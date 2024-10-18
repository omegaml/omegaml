from flask import render_template

from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView, mixin_for


class ListDetailMixin(mixin_for(BaseView)):
    list_template = '{self.segment}.html'
    detail_template = '{self.segment}_detail.html'

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
