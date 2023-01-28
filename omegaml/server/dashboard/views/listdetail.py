from flask import render_template
from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView, mixin_for
from textwrap import dedent


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
        summary = self.store.summary(name)
        meta.attributes['docs'] = meta.attributes.get('docs', '').strip() or self._default_markdown(meta)
        data = {
            'meta': meta.to_dict(),
            'summary': summary,
        }
        data.update(self.detail_data(name, data=data, meta=meta))
        return render_template(f"dashboard/{template}",
                               segment=self.segment,
                               buckets=self.buckets,
                               **data)

    def detail_data(self, name, data=None, meta=None):
        return {}

    def _default_markdown(self, meta):
        return dedent("""
        ## {metadata.name}
        
        A {meta.kind} object created on {meta.created} and last modified on {meta.modified}.
        
        > Edit this document to provide your own documentation in Markdown format. 
          You may use either [CommonMark](http://commonmark.org/) or [GFM](https://github.github.com/gfm/).
          
        > To access metadata, use {{metadata.key}} where key is the part of the metadata to show.
          For example, to show the object's kind, use {{metadata.kind}}. To access metadata.attributes,
          use {{attributes.key}}.    
        """)
