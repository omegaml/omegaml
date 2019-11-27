"""
Usage: om <command> [<action>] [<args> ...] [options]
       om (models|datasets|scripts|jobs) [<args> ...] [--raw] [--replace] [options]
       om runtime [<args> ...] [--async] [options]
       om cloud [<args> ...] [options]
       om shell [options]
       om [-h] [-hh] [--version] [--copyright]

omega|ml command line client

[usage:datasets]
[usage:models]
[usage:runtime]
[usage:scripts]
[usage:jobs]
[usage:cloud]
[usage:shell]

Options:
  -h --help          Show this screen
  -hh --help-ext     Show detailed descriptions
  --version          Show version.
  --loglevel=LEVEL   INFO,ERROR,DEBUG [default: INFO]
  --copyright        Show copyright
  --config=CONFIG    configuration file
  --bucket=BUCKET    the bucket to use
  --local-runtime    use local runtime

Options for datasets and models
  --raw  list Metadata objects instead of names only

[options:datasets]
[options:models]
[options:runtime]
[options:cloud]
[options:scripts]
[options:jobs]

[description:datasets]
[description:models]
[description:runtime]
[description:cloud]
[description:scripts]
[description:jobs]
"""
import sys

from omegaml import version
from omegaml.client.cli.catchall import GlobalCommand
from omegaml.client.cli.cloud import CloudCommand
from omegaml.client.cli.datasets import DatasetsCommand
from omegaml.client.cli.jobs import JobsCommand
from omegaml.client.cli.models import ModelsCommand
from omegaml.client.cli.runtime import RuntimeCommand
from omegaml.client.cli.scripts import ScriptsCommand
from omegaml.client.cli.shell import ShellCommand
from omegaml.client.docoptparser import DocoptParser


def main(argv=None, logger=None):
    # make sure cli sees current project
    sys.path.insert(0, '.')
    # use argv and logger for debugging and testing
    parser = DocoptParser(__doc__, [DatasetsCommand,
                                    ScriptsCommand,
                                    ModelsCommand,
                                    RuntimeCommand,
                                    CloudCommand,
                                    ShellCommand,
                                    JobsCommand,
                                    GlobalCommand],
                          argv=argv,
                          version=version,
                          logger=logger)
    parser.parse()
    parser.process()
    return parser

def climain():
    # entry point for distutils console_script
    main()

if __name__ == '__main__':
    main()
