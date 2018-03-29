define(['backbone'], function($B) {
    console.log('omegaml settings initialized');
    var settings = {
        debug : true,
        authApiUri : '/api/v2/auth',
        apiUrl : '/api/v1',
    };
    return settings;
});