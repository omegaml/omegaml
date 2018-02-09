define(['backbone', 'omegaweb.settings'], function($B, settings) {
    /**
     * Dataset. This provides access to an omegaml dataset
     */
    var Dataset = $B.Model.extend({
        page : 0,
        filterSpec: '',
        urlRoot : function() {
            // need to URI encode because dataset names can contain any
            // characters
            var dsName = encodeURIComponent(this.datasetName);
            return settings.apiUrl + '/dataset/{0}'.format([dsName]);
        },
        query : function() {
            return 'orient=record&page={0}&{1}&{2}'.format([this.page,
                this.filterSpec, this.qryQuery()]);
        },
        initialize : function(options) {
            this.datasetName = options.name;
            this.page = options.page || 0;
        },
        asCollection : function() {
            var that = this;
            var data = _.map(this.attributes.data.rows, function(v, i) {
                v.index = that.attributes.index.values[i];
                return v
            });
            return new $B.Collection(data);
        },
        nextPage : function() {
            this.page += 1;
        },
        previousPage : function() {
            this.page -= 1;
            this.page = this.page < 0 ? 0 : this.page;
        }
    });
    var objects = $B.Collection.extend({
        model : Dataset,
        url : settings.apiUrl + '/dataset/',
    });
    Dataset.objects = objects;
    return Dataset;
});
