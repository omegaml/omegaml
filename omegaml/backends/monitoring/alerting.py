from datetime import datetime, timedelta

from omegaml import defaults


class AlertRule:
    def __init__(self, monitor=None, event=None, action=None, recipients=None, since=None):
        from omegaml.backends.monitoring.base import DriftMonitorBase
        self.monitor: DriftMonitorBase = monitor
        self.event = event or 'drift'
        self.action = action
        self.recipients = recipients
        self.since = since or datetime.utcnow() - timedelta(seconds=defaults.OMEGA_MONITORING_DRIFT_INTERVAL)

    def check(self, notify=True, run=None):
        tracking = self.monitor.tracking
        run = run or '*'
        data = tracking.data(run=run, event='drift', since=self.since, raw=True)
        if notify and data:
            self.notify(self.recipients, data)
        self.last_check = datetime.utcnow()
        return bool(data)

    def notify(self, recipients, data):
        # log and send notification
        self.monitor.tracking.log_event('alert', self.monitor._drift_alert_key, data,
                                        recipients=recipients)

