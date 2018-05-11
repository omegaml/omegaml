/* this code is inserted verbatim into report.html */
$(function() {
    require(['omegaweb/js/models/report', 'backbone', 'jquery', 'reveal'], function(Report, $B, $, Reveal) {
        var report = new Report({
            name : context.name,
            format: 'slides',
        });
        if(window.location.hash.indexOf('html') > -1) {
            report.format = 'html';
        }
        if(window.location.search.indexOf('html') > -1) {
            report.format = 'html';
        }
        report.fetch({
            reset : true,
        }).done(function() {
            console.info('fetched report {0}'.format([report.format]));
            var content = report.get('content');
            var body = $('body');
            body.html(content);
            if(report.format == 'slides') {
                Reveal.initialize({
                     center:false,
                });
            }
        });
    });
});

