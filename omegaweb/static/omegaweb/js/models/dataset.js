define(['backbone', 'omegaweb.settings'], function($B, settings) {
    /**
     * Dataset. This provides access to an omegaml dataset
     */
    var Dataset = $B.Model.extend({
        urlRoot : settings.apiUrl + '/dataset/{0}/'.format([this.resource]),
    });
    var objects = $B.Collection.extend({
        model : Dataset,
        url : settings.apiUrl + '/dataset/',
    });
    Dataset.objects = objects;
    return Dataset;
});
