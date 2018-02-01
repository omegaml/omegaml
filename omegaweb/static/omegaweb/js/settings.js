define(['backbone'], function($B) {
    console.log('cleverpendeln settings initialized');
    var settings = {
        debug : true,
        authApiUri : '/api/v2/auth',
        apiUrl : '/api/v1',
    };
    $B.Tastypie.apiKey.username = 'test5';
    $B.Tastypie.apiKey.key = 'ba6a6d4bcc0af89e643ae64562e1dcd340f67100';
    return settings;
});