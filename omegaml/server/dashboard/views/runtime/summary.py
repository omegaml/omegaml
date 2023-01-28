from flask import render_template, request


def create_view(bp):
    import omegaml as om

    @bp.route('/runtime')
    def summary():
        workers = [
            {'name': 'worker-1', 'status': 'running', 'activity': '10% / 10'},
            {'name': 'worker-2', 'status': 'running', 'activity': '10% / 10'},
        ]
        return render_template('dashboard/runtime/summary.html',
                               segment='runtime',
                               items=workers,
                               attributes={},
                               buckets=['default'])

    @bp.route('/runtime/log')
    def logviewer():
        logdata = [
            {'datetime': '2020-01-01 00:00:00',
             'level': 'info',
             'name': 'worker-1',
             'hostname': 'worker-1',
             'userid': 'user-1',
             'text': 'this is a log message',
             }
        ]
        mdf = om.logger.dataset.get(lazy=True)
        # parse datatable serverside params
        start = int(request.args.get('start', 0))
        nrows = int(request.args.get('length', 10))
        query = request.args.get('search[value]', None)
        sortby_idx = request.args.get('order[0][column]', 0)
        sortby = request.args.get(f'columns[{sortby_idx}][data]', 'created')
        sortascending = 'desc' != request.args.get('order[0][dir]', 'desc')
        # filter and prepare log data
        logdata = (mdf
                   .skip(start)
                   .head(nrows)
                   .query(text__contains=query)
                   .value)
        if len(logdata) > 0:
            logdata = (logdata
                       .reset_index()
                       .sort_values(sortby, ascending=sortascending)
                       .to_dict(orient='records'))
        else:
            logdata = []
        return {
            'data': logdata,
            'recordsTotal': len(mdf),
            'recordsFiltered': len(logdata) if query else len(mdf),
        }

    @bp.route('/runtime/worker/<name>')
    def worker(name):
        return name




