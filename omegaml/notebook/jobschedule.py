import datetime
from croniter import croniter
import six
from celery.schedules import crontab


class JobSchedule(object):
    """
    Produce a cron tab spec from text, time periods, or a crontab spec

    Given any specification format, can translate to a human readable
    text.

    If using time periods (minute, hour, weekday, monthday, month),
    any argument not specified defaults to '*' for this argument.

    If using text, sepearate each time part (weekday, hour, month)
    by a comma. To specify multiple times for a part, use / instead
    of comma.

    Examples:
        # using text
        JobSchedule('friday, at 06:00/08:00/10:00')
        JobSchedule('Mondays and Fridays, at 06:00')
        JobSchedule('every 5 minutes, on weekends, in april')

        # using time periods
        JobSchedule(weekday='mon-fri', at='06:05,12:05')
        JobSchedule(weekday='mon-fri', at='06:00')
        JobSchedule(month='every 2', at='08:00', weekday='every 3')

        # using a crontab spec
        JobSchedule('05 06,12 * * mon-fri')

        # given a valid specification get human readable text or crontab format
        JobSchedule('05 06,12 * * mon-fri').text
        JobSchedule('Mondays and Fridays, at 06:00').cron

    Args:
        text: the natural language specification, with time parts
              separated by comma
        at: the hh:mm specification, equal to hour=hh, minute=mm
        minute: run on 0-59th minute in every specified hour
        hour: run on 0-23th hour on every specified day
        weekday: run on 0-6th day in every week (0 is Sunday),
                 can also be specified as mon/tue/wed/thu/fri/sat/sun
        monthday: run on 1-31th day in every month
        month: run on 1-12th day of every year

    Raises:
        ValueError if the given specification is not correct

    Returns:
        the cron specificiation, use for run_at in self.schedule()
    """

    def __init__(self, text=None, minute='*', hour='*', weekday='*',
                 monthday='*', month='*', at=None):
        # if we get text, attempt to convert
        if text:
            self.sched = self._convert_text(text).sched
            return
        # no text, but time periods
        # get times
        if at:
            # 06:00 => hour=6 / minute=00
            # 06:00,12:00 => hour=6,12 / minute=00
            hours, minutes = [], []
            for att in at.split(','):
                h, m = att.split(':')
                hours.append(h)
                minutes.append(m)
            hour = ','.join(sorted(set(hours)))
            minute = ','.join(sorted(set(minutes)))
        # every n => */n
        minute = self._expand_every(minute)
        hour = self._expand_every(hour)
        weekday = self._expand_every(weekday)
        monthday = self._expand_every(monthday)
        month = self._expand_every(month)
        # long to short, e.g. friday => fri
        weekday = self._convert_weekdays(weekday)
        # month to number, e.g. january = 1
        month = self._convert_months(month)
        # get a cron spec
        self.sched = crontab(minute=minute,
                             hour=hour,
                             day_of_month=monthday,
                             day_of_week=weekday,
                             month_of_year=month)
        # make sure the spec can be processed by croniter
        if not croniter.is_valid(self.cron):
            raise ValueError("{cronspec} is not a valid schedule")

    @classmethod
    def from_cron(cls, cronspec):
        (minute, hour, monthday, month, weekday) = cronspec.split(' ')
        return JobSchedule(minute=minute, hour=hour, monthday=monthday,
                           month=month, weekday=weekday)

    @classmethod
    def from_text(cls, text):
        return JobSchedule(text=text)

    @property
    def cron(self):
        # adopted from https://docs.celeryproject.org/en/latest/_modules/celery/schedules.html#schedule
        cron_repr = ('{0._orig_minute} {0._orig_hour} {0._orig_day_of_month} '
                     '{0._orig_month_of_year} {0._orig_day_of_week}')
        return cron_repr.format(self.sched)

    @property
    def text(self):
        from cron_descriptor import get_description
        return get_description(self.cron)

    def next_times(self, n=None, last_run=None):
        iter_next = croniter(self.cron, start_time=last_run)
        while n > 0 or n is None:
            yield iter_next.get_next(datetime.datetime)
            n -= 1 if n > 0 else None

    def __repr__(self):
        return 'JobSchedule(cron={}, text={})'.format(self.cron, self.text)

    def _convert_weekdays(self, v):
        # convert full name weekdays to short
        days = dict([('monday', 'mon'),
                     ('tuesday', 'tue'),
                     ('wednesday', 'wed'),
                     ('thursday', 'thu'),
                     ('friday', 'fri'),
                     ('saturday', 'sat'),
                     ('sunday', 'sun'),
                     ('weekday', 'mon-fri'),
                     ('workday', 'mon-fri'),
                     ('working day', 'mon-fri'),
                     ('weekend', 'sat-sun'),
                     ('week-end', 'sat-sun'),
                     ('week end', 'sat-sun'),
                     ])
        v = v.lower()
        for full, short in days.items():
            v = v.replace(full, short)
        return v

    def _has_month(self, v):
        months = ('january,february,march,april,may,june,july,august,'
                  'september,october,november,december').split(',')
        long = any(m in v for m in months)
        short = any(m[0:3] in v for m in months)
        return long or short

    def _has_day(self, v):
        days = ('monday,tuesday,wednesday,thursday,friday,saturday,sunday').split(',')
        long = any(d in v for d in days)
        short = any(d[0:3] in v for d in days)
        return long or short

    def _convert_months(self, v):
        months = ('january,february,march,april,may,june,july,august,'
                  'september,october,november,december').split(',')
        if not self._has_month(v):
            return v
        v = v.lower()
        for m in months:
            # full
            start = v.find(m)
            if start > -1:
                v = v.replace(m, str(months.index(m) + 1))
            # short
            sm = m[0:3]
            start = v.find(sm)
            if start > -1:
                v = v.replace(sm, str(months.index(m) + 1))
        return v

    def _expand_every(self, v):
        # convert 'every' specs to cron-like
        if not isinstance(v, six.string_types):
            return v
        # every n(nd,rd,th) => */n
        if '1st' in v or 'first' in v:
            # 'every 1st' => 1
            v = '1'
        if v.startswith('every '):
            v = v.replace('every ', '*/')
            for order in ('nd', 'rd', 'th'):
                v = v.replace(order, '')
        else:
            # 'every' => *
            v = v.replace('every', '*')
        return v.strip()

    def _convert_text(self, text):
        # experimental natural language text to crontab
        # every friday
        specs = {}
        # ensure single whitespace
        orig_text = text
        text = ' '.join(text.split(' ')).lower()
        # try placing commas
        text = text.replace(' ', ',')
        text = text.replace('every,', 'every ')
        text = text.replace(',and,', ' and ')
        text = text.replace(',only,', ' only ')
        text = text.replace('at,', 'at ')
        text = text.replace('on,', 'on ')
        text = text.replace('in,', 'in ')
        text = text.replace(',through,', ' through ')
        text = text.replace(',-,', ' - ')
        text = text.replace(',until,', ' until ')
        text = text.replace(',till,', ' till ')
        text = text.replace(',to,', ' to ')
        text = text.replace(',of,', ' of ')
        text = text.replace(',from,', ' from ')
        text = text.replace(',hours,', ' hours,')
        text = text.replace(',hour,', ' hour,')
        text = text.replace('day hour,', 'day,hour ')
        text = text.replace('hours,', 'hours ')
        text = text.replace('hour,', 'hour ')
        text = text.replace('working,day', 'working day')
        text = text.replace('week,day', 'week day')
        text = text.replace(',minutes', ' minutes')
        text = text.replace(',minute', ' minute')
        text = text.replace(',day', ' day')
        text = text.replace(',end', ' end')
        text = text.replace(',month,', ' month,')
        # get parts separated by comma
        parts = [part.strip() for part in text.split(',') if part]
        try:
            specs = self._parse_parts(parts)
            sched = JobSchedule(**specs)
        except:
            raise ValueError(f'Cannot parse {orig_text}, read as {parts}')
        return sched

    def _parse_parts(self, parts):
        specs = {}
        for part in parts:
            # Monday and Friday => Monday/Friday
            part = part.replace(' and ', ',')
            part = part.replace('days', 'day')
            part = part.replace('hours', 'hour')
            part = part.replace('minutes', 'minute')
            part = part.replace('ends', 'end')
            part = part.replace('on ', '')
            part = part.replace('in ', '')
            part = part.replace('/', ',')
            part = part.replace(' through ', '-')
            part = part.replace(' until ', '-')
            part = part.replace(' till ', '-')
            part = part.replace(' to ', '-')
            part = part.replace(' of ', '')
            part = part.replace('from ', '')
            if 'day' in part and 'month' in part:
                specs['monthday'] = part.replace('day', '').replace('month', '')
            elif 'month' in part:
                # 'every month', 'every 3rd month'
                specs['month'] = part.replace('month', '').strip()
            elif self._has_month(part):
                # 'january', 'every january'
                specs['month'] = self._convert_months(part).replace('every', '')
            elif 'daily' in part:
                specs['weekday'] = '*'
            elif (self._has_day(part) or 'day' in part or 'week' in part):
                # 'monday-friday', 'tuesday', 'every 3rd day'
                part = (self._convert_weekdays(part)
                        .replace('day', '')
                        .strip())
                # every mon-fri => mon-fri
                if 'every ' in part and '-' in part:
                    part = part.replace('every ', '').strip()
                specs['weekday'] = part
            elif ':' in part:
                # at 06:00
                specs['at'] = part.replace('at', '').strip()
            elif 'hour' in part:
                # every hour, hour 6, hour 6/7
                specs['hour'] = part.replace('hour', '').strip()
            elif 'minute' in part:
                # every minute, every 3rd minute, every 5 minutes, minute 6/7
                specs['minute'] = part.replace('minute', '').replace('at ', '').strip()
        return specs
