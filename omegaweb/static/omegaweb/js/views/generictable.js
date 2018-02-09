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
            var columns = view.columns;
            if (this.collection) {
                view.grid = new Backgrid.Grid({
                    collection : view.collection,
                    columns : columns,
                    emptyText : "no data",
                    row : FocusableRow,
                });
                view.$('div.table-responsive').append(view.grid.render().el);
                this.collection.on('model:edit', function(model) {
                    view.trigger('row:edit', model)
                });
            }
        },
        update : function(collection) {
            var view = this;
            if (view.grid) {
                view.grid.collection.reset(collection.models);
                view.grid.render();
                this.collection.on('model:edit', function(model) {
                    view.trigger('row:edit', model)
                });
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
    // https://github.com/ericmaicon/backgrid/blob/master/src/cell.js
    Backgrid.ButtonCell = Backgrid.Cell.extend({
        events : {
            'click' : function() {
                this.model.collection.trigger('model:edit', this.model);
            }
        },
        render : function() {
            this.$el.empty();
            var button = $("<a>", {
                href : 'javascript:;',
                'class' : 'btn ' + this.column.attributes.btnClassName,
                text : this.column.attributes.btnText,
            });
            if (this.column.attributes.icon) {
                button.append('<i class="{0}"><i>'
                    .format([this.column.attributes.icon]));
            }
            this.$el.append(button);
            this.delegateEvents();
            return this;
        }
    });
    // https://github.com/cloudflare/backgrid/issues/489#issuecomment-43818169
    Backgrid.FixedWidthCell = Backgrid.Cell.extend({
        className : 'fixed',
        enterEditMode : function() {
            this.$el.width((this.$el.outerWidth() - 10) + 'px');
            Backgrid.Cell.prototype.enterEditMode.apply(this, arguments);
        },
        exitEditMode : function() {
            this.$el.width(false);
            Backgrid.Cell.prototype.exitEditMode.apply(this, arguments);
        }
    });
    var FocusableRow = Backgrid.Row.extend({
        highlightColor : "lightGray",
        events : {
            click : "rowFocused",
            focusout : "rowLostFocus"
        },
        rowFocused : function() {
            this.previousColor = this.el.style.backgroundColor;
            this.el.style.backgroundColor = this.highlightColor;
        },
        rowLostFocus : function() {
            this.el.style.backgroundColor = this.previousColor;
        }
    });
    return GenericTableView;
});