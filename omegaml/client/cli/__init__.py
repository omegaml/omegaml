"""
Usage: om <command> [<action>] [<args>...] [options]
       om (models|datasets|scripts|jobs) [<args>...] [--replace] [--csv...] [options]
       om runtime [<args>...] [--async] [--result] [--param] [options]
       om cloud [<args>...] [options]
       om shell [<args>...] [options]
       om help [<command>]

[usage:datasets]
[usage:models]
[usage:runtime]
[usage:scripts]
[usage:jobs]
[usage:cloud]
[usage:shell]

Options:
  -h, --help         Show this screen
  --version          Show version.
  --loglevel=LEVEL   INFO,ERROR,DEBUG [default: INFO]
  --copyright        Show copyright
  --config=CONFIG    configuration file
  --bucket=BUCKET    the bucket to use
  --local-runtime    use local runtime
  -q, --noinput      don't ask for user input, assume yes
  -E                 treat patterns as regular expressions

[options:datasets]
[options:models]
[options:runtime]
[options:cloud]
[options:scripts]
[options:jobs]
[options:shell]

[description:datasets]
[description:models]
[description:runtime]
[description:cloud]
[description:scripts]
[description:jobs]
[description:shell]
"""
import sys

from omegaml import version
from omegaml.client.cli.catchall import CatchallCommandBase
from omegaml.client.cli.cloud import CloudCommandBase
from omegaml.client.cli.datasets import DatasetsCommandBase
from omegaml.client.cli.jobs import JobsCommandBase
from omegaml.client.cli.models import ModelsCommandBase
from omegaml.client.cli.runtime import RuntimeCommandBase
from omegaml.client.cli.scripts import ScriptsCommandBase
from omegaml.client.cli.shell import ShellCommandBase
from omegaml.client.docoptparser import CommandParser


def main(argv=None, logger=None, **kwargs):
    # make sure cli sees current project
    sys.path.insert(0, '.')
    # use argv and logger for debugging and testing
    parser = CommandParser(__doc__, [DatasetsCommandBase,
                                     ScriptsCommandBase,
                                     ModelsCommandBase,
                                     RuntimeCommandBase,
                                     CloudCommandBase,
                                     ShellCommandBase,
                                     JobsCommandBase,
                                     CatchallCommandBase],
                           argv=argv,
                           version=version,
                           logger=logger,
                           **kwargs)
    try:
        parser.parse()
        parser.process()
    except Exception as e:
        print(f"*** ERROR {e}")
        if parser.should_debug:
            raise
        exit(1)
    return parser


def climain():
    # entry point for distutils console_script
    main()


if __name__ == '__main__':
    main()
