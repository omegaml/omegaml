/* this code is inserted verbatim into dataset.html */
$(function() {
    require(['omegaweb/js/views/generictable',
        'omegaweb/js/models/dataset', 'omegaweb/js/models/model',
        'backbone'], function(GenericTableView, Dataset, Model, $B) {
        function column(name, label, cell, options) {
            options = options || {};
            var coldef = {
                name : name,
                label : label,
                cell : cell || 'fixed-width',
                width : 1,
                editable : true,
                btnClassName : 'btn-info',
                btnText: '',
                icon: 'far fa-table',
            };
            return _.defaults(options, coldef);
        };;
        var dataset = new Dataset({
            name : context.name,
        });
        /* display  */
        dataset.fetch({
            reset : true,
        }).done(function() {
            console.info('fetched dataset {0}, rendering..'
                .format([context.name]));
            var dataColumns = _.map(_.keys(dataset.attributes.dtypes), function(k) {
                return column(k, k, 'fixed-width', { editable: false });
            });
            var indexColumn = [column('index', 'Index')];
            var tableOptions = {
                columns : indexColumn.concat(dataColumns),
            };
            var datasetView = new GenericTableView({
                el : '.panel.datasets',
                tableOptions : tableOptions,
                collection : dataset.asCollection(),
            });
            datasetView.render();
            $('.search').on('click', function() {
                dataset.filterSpec = $('.filterkw').val();
                dataset.fetch({reset:true}).done(function() {
                    dataset.page = 0;
                    datasetView.update(dataset.asCollection());
                })
            });
            $('.search-form').keypress(function(e){
                if(e.which == 13){//Enter key pressed
                    $('.search').click();//Trigger search button click event
                }
            });
            $('.nextpage').on('click', function() {
                dataset.nextPage();
                $('a.pageno').text(dataset.page + 1);
                dataset.filterSpec = $('.filterkw').val();
                dataset.fetch({reset:true}).done(function() {
                    datasetView.update(dataset.asCollection());
                })
            });
            $('.prevpage').on('click', function() {
                dataset.previousPage();
                $('a.pageno').text(dataset.page + 1);
                dataset.fetch({reset:true}).done(function() {
                    datasetView.update(dataset.asCollection());
                })
            });
        }).error(function() {
            alert("there was an error");
        });
    });
});