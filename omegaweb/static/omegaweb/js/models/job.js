define(['backbone', 'omegaweb.settings'], function($B, settings) {
    /**
     * Dataset. This provides access to an omegaml dataset
     */
    var Job = $B.Model.extend({
        urlRoot : settings.apiUrl + '/job/{0}/'.format([this.resource]),
    });
    var objects = $B.Collection.extend({
        model : Job,
        url : settings.apiUrl + '/job/',
    });
    Job.objects = objects;
    return Job;
});
