define(['backbone', 'omegaweb.settings'], function($B, settings) {
    /**
     * Dataset. This provides access to an omegaml dataset
     */
    var Report = $B.Model.extend({
        urlRoot : function() {
            return settings.apiUrl + '/job/{0}/report/'.format([this.name]);
        },
        initialize: function(options) {
            this.name = options.name;
            this.format = options.format || 'html';
        },
        query: function() {
            return 'fmt={0}'.format([this.format]);
        }
    });
    return Report;
});
