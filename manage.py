#!/usr/bin/env python
import os
import sys
import warnings

from stackable.stackable import StackableSettings

if '--trace' in ' '.join(sys.argv):
    tracef = open('trace.log', 'w')
    def trace(frame, event, arg):
        tracef.write("%s, %s:%d\n" %
                     (event, frame.f_code.co_filename, frame.f_lineno))
        return trace

    sys.settrace(trace)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
    # omegaweb should always be started without a security context USERID/APIKEY since:
    # - it is the "top level" authenticator to clients that are started with security
    # - if it starts with a security context, it will enter endless recursion
    # - Also see wsgi.py
    if any(k in os.environ for k in ('OMEGA_USERID', 'OMEGA_APIKEY')):
        warnings.warn('omegaweb ignores OMEGA_USERID/OMEGA_APIKEY found in env')
        os.environ.pop('OMEGA_USERID', None)
        os.environ.pop('OMEGA_APIKEY', None)

    from django.core.management import execute_from_command_line
    StackableSettings.parse_options()
    execute_from_command_line(sys.argv)
