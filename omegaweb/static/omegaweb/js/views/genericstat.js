define(['jquery', 'backbone', 'shrebo.util', 'datatables',
    'datatables-bootstrap', 'datatables-colreorder'], function($, $B, util) {
    /**
     * Generic stats table based on jq Datatables
     * 
     * Works with models.GenericStats by taking the data provided
     * by the latter and passing it on to Datatables. Uses the
     * colReorder plugin to adjust column orders.
     * 
     * Note that the data formatting is transparent to GenericStatsView
     * as it happens in the model. If you need to override formatting
     * behavior, either check GenericStats.formatData or pass another
     * model that does the appropriate formatting. 
     * 
     * Alternative model
     * 
     * You may pass any model as long as it has .columns and .data
     * attributes comformant with Datatables format.
     */
    var GenericStatsView = $B.View.extend({
        events : {
            'click .action-export' : 'exportCsv',
        },
        /**
         * Pass data as follows
         * 
         * <pre>
         * { 
         *   columns : array of columns
         *   data : array of array of per-row data, same order as columns
         * }
         * </pre>
         * 
         * Available options
         * 
         * <pre>
         * colDefs = {
         *    'colname' : {
         *         visible : true|false,
         *         position: #,
         *    },
         * }
         * </pre>
         * 
         * Note this is the same as Python Pandas' to_dict('strip') format as
         * specified here
         * http://pandas.pydata.org/pandas-docs/dev/generated/pandas.DataFrame.to_dict.html
         * 
         * @param data
         *            data as specified above
         * @param options
         *            options as above
         */
        initialize : function(options) {
            this.render();
            this.colDefs = options.colDefs || null;
        },
        render : function() {
            var view = this;
            if (this.model) {
                this.model.fetch().done(function() {
                    var data = view.model.get('data');
                    if (data) {
                        view.table && view.table.destroy(false);
                        var table = $(view.el).find('table');
                        $(table).empty(); // empty in case the columns change
                        console.debug('model data received');
                        var dtOptions = {
                            scrollX : true,
                            data : data,
                            columns : _
                                .map(view.model.get('columns'), function(c) {
                                    return {
                                        'title' : view.model.columnLabel(c),
                                        'visible' : view.getColDefs(c).visible,
                                        'width' : view.getColDefs(c).width,
                                    };
                                }),
                        };
                        // initialize the table
                        $(table).dataTable(dtOptions);
                        view.table = $(table).DataTable();
                        view.setColOrder();
                        view.table.columns.adjust().draw();
                    }
                });
            }
        },
        getColDefs : function(c) {
            this.colDefs = this.colDefs || this.model.meta.columns; 
            return this.colDefs[c] || {};
        },
        setColOrder : function() {
            try {
             // set column ordering
                this.colReorder = new $.fn.dataTable.ColReorder(this.table);
                var model = this.model;
                var order = {};
                var columns = model.get('columns');
                var colDefs = this.colDefs;
                this.colReorder.fnOrder(this.rankColumns(columns, colDefs));
            } catch(e) {
                console.debug(e);
            }
        },
        /**
         * determine sort order of columns
         * 
         * works by finding the index of a column in columns, determining its
         * rank given the colDefs.position or by its default position. Ties are
         * broken by reducing the rank by 1/1000 until there is no lower rank
         * (e.g. rank would be 2, but column 2 is already set, so go from 2 to >
         * 1 by reducing rank). This is the poor man's version of insert at
         * position.
         * 
         * <pre>
         * var columns = ['a', 'b', 'c'];
         * //columns, index = sort order
         * var colDefs = {
         *   'a' : {
         *     position : 1
         *   },
         *   'b' : {
         *     position : 1
         *   }
         * };
         * var order = rankColumns(columns, colDefs)
         * =&gt; [1, 0, 2] // 'b', 'a', 'c' 
         * </pre>
         * 
         * @param columns
         *            array of column names, names map into colDefs
         * @param colDefs
         *            dict { column > .position }
         * @return ordered array of column indicies into columns
         */
        rankColumns : function(columns, colDefs) {
            var order = {};
            // determine rank of each column
            // order will be { rank => index } 
            _.each(columns, function(col, i) {
                var coldef = colDefs[col];
                var pos = coldef ? coldef.position || i : i;
                while (order[pos] >= 0) {
                    pos = pos - 1 / 1000;
                }
                order[pos] = i;
            });
            // finally, sort by rank value, map to column index
            var sorted = _.keys(order).sort(function(a, b) {
                return parseFloat(a) - parseFloat(b);
            });
            order = _.map(sorted, function(k) {
                return order[k];
            });
            return order;
        },
        exportCsv : function(e) {
            var target = e.target;
            util.csvExporter.exportTo({
                columns : this.model.get('columns'),
                rows : this.model.get('data'),
                filename : 'download.csv',
            }, target);
        },
    });
    return GenericStatsView;
});