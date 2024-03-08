from datetime import datetime


class AlertRule:
    def __init__(self, monitor=False, event=None, action=None, recipients=None):
        self.monitor = monitor
        self.event = event or 'drift'
        self.action = action
        self.recipients = recipients
        self.last_check = None

    def check(self):
        tracking = self.monitor.tracking
        data = tracking.data(run='*', event='drift', since=self.last_check, raw=True)
        if data:
            self.notify(self.recipients, data)
        self.last_check = datetime.utcnow()

    def notify(self, recipients, data):
        # send notification
        pass
