define(['jquery', 'backbone',//
        'chartjs', 'btselect', 'palette', 'shrebo.util'], function($, $B, Chart, btselect, palette, util) {
    var GenericGraphView = Backbone.View.extend({
        events : {
            'click .action-refresh' : 'refresh'
        },
        /**
         * options.data must be a valid series array for flot, see
         * https://github.com/flot/flot [ series1, series2, ... ]
         * 
         * where series# is [ [x1, y1], [x2, y2], ... ]
         */
        initialize : function(options) {
            this.render();
            this.defaults = options.defaults || {};
            this.graphOptions = _.clone(options.graphOptions) || {};
            this.chartType = this.graphOptions.chartType || 'bar';
            delete this.graphOptions.chartType;
        },
        render : function() {
            var view = this;
            view.progressEl = this.$('.with-progressbar');
            if (this.model) {
                view.progress = util.progressBar(view.progressEl).auto(1, .01);
                view.model.qryFilter('orient', 'list');
                view.model.fetch().done(function() {
                    console.debug('model data received');
                    if(view.model.meta.total_count > 0) {
                        view.progress && view.progress.remove();
                        view.defaults.labels = view.defaults.labels
                            || view.model.keys()[0];
                        view.defaults.values = view.defaults.values
                            || view.model.keys();
                        view.renderOptions();
                        view.renderGraph();
                    } else {
                        //util.notify("Keine Daten");
                    }
                });
            }
            $('.tgraph-label').selectpicker();
            $('.tgraph-values').selectpicker();
        },
        /**
         * render graph
         */
        renderGraph : function() {
            var view = this;
            // get graph data
            var data = {
                labels : view.getLabels(),
                datasets : view.getDatasets(),
            };
            var options = view.graphOptions;
            // create graph
            var graph = $(view.el).find('.graph');
            if (graph) {
                var ctx = graph.get(0).getContext("2d");
                var chart = new Chart(ctx);
                view.chart && view.chart.destroy();
                // http://www.chartjs.org/docs/#getting-started
                switch (view.chartType) {
                    case 'bar' :
                        view.chart = chart.Bar(data, options);
                        break;
                    case 'line' :
                        view.chart = chart.Line(data, options);
                        break;
                    default :
                        console.error('invalid chart type {0}'
                            .format([view.chartType]));
                }
            }
        },
        /**
         * render option selectors from model data
         */
        renderOptions : function() {
            // this.$ doesn't work because .selectpicker is not present
            // $(this.el) uses the global $ and has .selectpicker installed
            var label = $(this.el).find('select.tgraph-label');
            var values = $(this.el).find('select.tgraph-values');
            var view = this;
            var model = this.model;
            label.empty();
            values.empty();
            _.each(_.keys(model.attributes), function(k) {
                // select default options
                var labelSelected = view.defaults.label == k ? 'selected' : '';
                var valueSelected = view.defaults.values.indexOf(k) > -1
                    ? 'selected'
                    : '';
                // add options
                var columnLabel = model.columnLabel(k);
                label.append("<option value='{0}' {1}>{2}</option>".format([k,
                    labelSelected, columnLabel]));
                values.append("<option value='{0}' {1}>{2}</option>".format([k,
                    valueSelected, columnLabel]));
            });
            label.selectpicker('refresh');
            values.selectpicker('refresh');
        },
        getLabels : function() {
            var label = this.$('select.tgraph-label option:selected');
            return this.model.get(label.val());
        },
        getDatasets : function() {
            var view = this;
            var values = this.$('select.tgraph-values option:selected');
            var colors = _
                .map(palette('sequential', values.length + 1), function(c) {
                    return "#" + c;
                });
            var datasets = _.map(values, function(v, i) {
                var col = this.$(v).val();
                var color = colors[i + 1]; // ignore the first color as it is
                // white-ish (invisible on white
                // background...)
                return {
                    label : col,
                    fillColor : color,
                    strokeColor : color,
                    pointColor : color,
                    highlightFill : color,
                    highlightStroke : color,
                    data : view.model.get(col),
                    datasetFill : false,
                }
            });
            return datasets;
        },
        refresh : function() {
            this.renderGraph();
        }
    });
    return GenericGraphView;
});