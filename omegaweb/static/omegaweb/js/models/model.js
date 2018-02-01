define(['backbone', 'omegaweb.settings'], function($B, settings) {
    /**
     * Dataset. This provides access to an omegaml dataset
     */
    var Model = $B.Model.extend({
        urlRoot : settings.apiUrl + '/model/{0}/'.format([this.resource]),
    });
    var objects = $B.Collection.extend({
        model : Model,
        url : settings.apiUrl + '/model/',
    });
    Model.objects = objects;
    return Model;
});
