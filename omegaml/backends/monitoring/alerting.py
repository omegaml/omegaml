from datetime import datetime


class AlertRule:
    def __init__(self, monitor=None, event=None, action=None, recipients=None):
        from omegaml.backends.monitoring.base import DriftMonitorBase
        self.monitor: DriftMonitorBase = monitor
        self.event = event or 'drift'
        self.action = action
        self.recipients = recipients
        self.last_check = None

    def check(self, notify=True, run=None):
        tracking = self.monitor.tracking
        run = run or '*'
        data = tracking.data(run=run, event='drift', since=self.last_check, raw=True)
        if notify and data:
            self.notify(self.recipients, data)
        self.last_check = datetime.utcnow()
        return bool(data)

    def notify(self, recipients, data):
        # send notification
        # TODO this should just log the alert, not send it
        #      we should have a stream/task(?) that checks for alerts and sends them (?)
        self.monitor.tracking.log_event('alert', self.monitor._drift_alert_key, data,
                                        recipients=recipients)
