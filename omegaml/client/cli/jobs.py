import datetime
import nbformat
from cron_descriptor import get_description
from omegaml.client.docoptparser import CommandBase

from omegaml.client.util import get_omega


class JobsCommandBase(CommandBase):
    """
    Usage:
      om jobs list [<pattern>] [--raw] [options]
      om jobs put <path> <name> [options]
      om jobs get <name> <path> [options]
      om jobs drop <name>
      om jobs metadata <name> [options]
      om jobs schedule <name> [show|delete|<interval>] [options]
      om jobs status <name>

    Options:
      --cron <spec>       the cron spec, use https://crontab.guru/
      --weekday <wday>    a day number 0-6 (0=Sunday)
      --monthday <mday>   a day of the month 1-31
      --month <month>     a month number 1-12
      --at <hh:mm>        the time (same as --hour hh --minute mm)
      --hour <hour>       the hour 0-23
      --minute <minute>   the minute 0-59
      --next <n>          show next n triggers according to interval

    Description:
        Specify the schedule either as

        * a natural language-like text, with any time components separated
          by comma

          om jobs schedule myjob "every 5 minutes, on fridays, in april"
          om jobs schedule myjob "at 6:00, on fridays"
          om jobs schedule myjob "at 6:00/10:00, on fridays"
          om jobs schedule myjob "every 2nd hour, every 15 minutes, weekdays"


    """
    command = 'jobs'

    def list(self):
        om = get_omega(self.args)
        raw = self.args.get('--raw', False)
        pattern = self.args.get('<pattern>')
        entries = om.jobs.list(pattern=pattern, raw=raw)
        self.logger.info(entries)

    def put(self):
        from nbformat import read as nbread

        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        with open(local, 'rb') as fin:
            nb = nbread(fin, as_version=4)
        self.logger.info(om.jobs.put(nb, name))

    def get(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        notebook = om.jobs.get(name)
        nbformat.write(notebook, local)
        self.logger.debug(local)

    def metadata(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.jobs.metadata(name).to_json())

    def plugins(self):
        om = get_omega(self.args)
        for kind, plugincls in om.defaults.OMEGA_STORE_BACKENDS.items():
            self.logger.info(kind, plugincls.__doc__)

    def drop(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.jobs.drop(name))

    def schedule(self):
        # FIXME this is a mess
        om = get_omega(self.args)
        name = self.args.get('<name>')
        at = self.args.get('--at')
        # get interval specs
        if at:
            hour, minute = at.split(':')
        else:
            hour = self.args.get('--hour')
            minute = self.args.get('--minute')
        weekday = self.args.get('--weekday')
        monthday = self.args.get('--monthday')
        month = self.args.get('--month')
        delete = self.args.get('delete')
        show = self.args.get('show')
        spec = self.args.get('--cron')
        next_n = self.args.get('--next')
        interval = self.args.get('<interval>')
        # by default we show if no interval is specified
        show = show or not any(s for s in (weekday, monthday, month, hour, minute, interval, spec))
        # print current schedule and triggers
        run_at, triggers = om.jobs.get_schedule(name, only_pending=True)
        if run_at:
            human_sched = get_description(run_at)
            self.logger.info("Currently {name} is scheduled at {human_sched}".format(**locals()))
            if next_n:
                self.logger.info("Given this existing interval, next {next_n} times would be:".format(**locals()))
                for time in om.jobs.Schedule.from_cron(run_at).next_times(int(next_n)):
                    self.logger.info("  {}".format(time))
        else:
            self.logger.info("Currently {name} is not scheduled".format(**locals()))
        # show current triggers
        if triggers:
            trigger = triggers[-1]
            if trigger['status'] == 'PENDING':
                event = trigger['event']
                self.logger.info("{name} is scheduled to run next at {event}".format(**locals()))
        # delete if currently scheduled
        if delete:
            if run_at or triggers:
                answer = self.ask("Do you want to delete this schedule?", options='Y/n', default='y')
                should_drop = answer.lower().startswith('y')
                return om.jobs.drop_schedule(name) if should_drop else None
        # create new schedule
        if not (show or delete):
            if interval:
                try:
                    # nlp text-like
                    spec = om.jobs.Schedule(interval).cron
                except Exception as e:
                    self.logger.info(f"Cannot parse {interval}, error was {e}")
                    raise
            if not spec:
                cron_repr = ('{0._orig_minute} {0._orig_hour} {0._orig_day_of_month} '
                             '{0._orig_month_of_year} {0._orig_day_of_week}')
                sched = om.jobs.Schedule(minute=minute or '*',
                                         hour=hour or '*',
                                         monthday=monthday or '*',
                                         weekday=weekday or '*',
                                         month=month or '*')
                cron_sched = sched.cron
            else:
                cron_sched = spec
            human_sched = get_description(cron_sched)
            if next_n:
                self.logger.info("Given this new interval, next {next_n} times would be:".format(**locals()))
                for time in om.jobs.Schedule.from_cron(cron_sched).next_times(int(next_n)):
                    self.logger.info("  {}".format(time))
            text = "Do you want to schedule {name} at {human_sched}?".format(**locals())
            answer = self.ask(text, options="Y/n", default='y')
            if answer.lower().startswith('n'):
                self.logger.info('Ok, not scheduled. Try again.')
                return
            self.logger.info('{name} will be scheduled to run {human_sched}'.format(**locals()))
            om.jobs.schedule(name, run_at=cron_sched, last_run=datetime.datetime.utcnow())

    def status(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        meta = om.jobs.metadata(name)
        attrs = meta.attributes
        runs = attrs.get('job_runs', [])
        run_at, triggers = om.jobs.get_schedule(name, only_pending=True)
        self.logger.info("Runs:")
        for run in runs:
            self.logger.info("  {ts} {status} ".format(**run))
        self.logger.info("Next scheduled runs:")
        for trigger in triggers:
            trigger['ts'] = trigger.get('ts', '')
            self.logger.info("  {ts} {status} {event-kind} {event}".format(**trigger))
