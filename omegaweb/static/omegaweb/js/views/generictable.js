define(['jquery', 'backbone', 'shrebo.util', 'backgrid', 'backgrid-select-all'], function($, $B, util, Backgrid) {
    /**
     * Generic data table based on backgrid.js
     * 
     * Works with any collection model by taking the data provided by the latter
     * and passing it on to Datatables. Uses the colReorder plugin to adjust
     * column orders.
     */
    var GenericTableView = $B.View.extend({
        events : {
            'click .action-export' : 'exportCsv',
            'click .action-search' : 'search',
        },
        initialize : function(options) {
            this.columns = options.tableOptions.columns;
        },
        render : function() {
            var view = this;
            if (this.collection) {
                view.grid = new Backgrid.Grid({
                    collection : view.collection,
                    columns : view.columns, 
                    emptyText : "no data",
                });
                view.$('div.table-responsive').append(view.grid.render().el);
            }
        },
        exportCsv : function(e) {
            var target = e.target;
            var view = this;
            util.csvExporter.exportTo({
                columns : _.keys(view.collection.first().attributes),
                rows : view.collection.map(function(item) {
                    return _.values(item.attributes);
                }),
                filename : 'download.csv',
            }, target);
        },
        search : function(e) {
            var qterm = this.$('.search-term').val();
            var query = this.collection.clearQryFilter();
            if ($.trim(qterm).length > 0) {
                query.qryFilter('username', qterm);
            }
            query.fetch({
                reset : true
            });
        }
    });
    return GenericTableView;
});