from flask import render_template, abort

from omegaml.backends.virtualobj import virtualobj
from omegaml.server import flaskview as fv
from omegaml.server.dashboard.views.base import BaseView


class PlotcardsView(BaseView):
    @fv.route('/{self.segment}')
    def index(self):
        abort(404) if not self.enabled else None
        om = self.om
        cards = om.scripts.list('cards/*', raw=True)
        return render_template('dashboard/miniapps/cards.html', segment=self.segment, cards=cards)

    @fv.route('/{self.segment}/<path:name>')
    def plotcards(self, name):
        # Create sample plots
        abort(404) if not self.enabled else None
        plots = []
        om = self.om
        name = name.replace('.html', '').replace(f'{self.segment}/', '')
        fqname = f'{self.segment}/{name}'
        result = []
        if om.scripts.exists(fqname):
            plotfn = om.scripts.get(fqname)
            if isinstance(plotfn, list):
                result = plotfn
            elif callable(plotfn):
                result = plotfn()
        for i, plot in enumerate(result):
            if isinstance(plot, dict):
                plots.append(plot)
            else:
                plots.append({'plot': plot, 'title': 'Plot '})
        return render_template('dashboard/miniapps/plotcards.html', segment=self.segment, name=name, plots=plots)

    @property
    def enabled(self):
        return getattr(self.om.defaults, 'OMEGA_CARDS_ENABLED') or self.app.config.get('CARDS_ENABLED', False)


@virtualobj
def myplots(*args, **kwargs):
    import plotly.express as px
    import plotly.io as pio

    plots = []
    # Example plot 1
    df1 = px.data.iris()
    fig1 = px.scatter(df1, x="sepal_width", y="sepal_length", color="species")
    plots.append({
        'content': pio.to_html(fig1, full_html=False),
        'title': 'Iris Sepal Width vs Sepal Length',
    })
    # Example plot 2
    df2 = px.data.gapminder()
    fig2 = px.line(df2, x="year", y="lifeExp", color="continent")
    plots.append({
        'content': pio.to_html(fig2, full_html=False),
        'title': 'Gapminder Life Expectancy',
    })
    fig1.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        autosize=True
    )
    fig2.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        autosize=True
    )
    return plots


def create_view(bp):
    view = PlotcardsView('cards')
    view.create_routes(bp)
    return
