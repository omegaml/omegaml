var omegawebConfig = requirejs
    .config({
        paths : {
            'datatables' : '/static/omegaweb/js/libs/datatables.net/jquery.dataTables',
            'backgrid' : '/static/omegaweb/js/libs/backgrid/libs/backgrid',
            'backgrid-select-all' : '/static/omegaweb/js/libs/backgrid-select-all/backgrid-select-all',
            'omegaweb.settings' : '/static/omegaweb/js/settings',
            'reveal': 'https://cdnjs.cloudflare.com/ajax/libs/reveal.js/3.6.0//js/reveal',
        }
    });