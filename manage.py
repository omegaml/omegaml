#!/usr/bin/env python
import os
from stackable.stackable import StackableSettings
import sys

import sys

tracef = open('trace.log', 'w')

if '--trace' in ' '.join(sys.argv):
    def trace(frame, event, arg):
        tracef.write("%s, %s:%d\n" %
                     (event, frame.f_code.co_filename, frame.f_lineno))
        return trace

    sys.settrace(trace)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

    from django.core.management import execute_from_command_line
    StackableSettings.parse_options()
    execute_from_command_line(sys.argv)
