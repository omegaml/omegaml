#!/usr/bin/env python
import os
from stackable.stackable import StackableSettings
import sys
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

    from django.core.management import execute_from_command_line
    StackableSettings.parse_options()
    execute_from_command_line(sys.argv)
