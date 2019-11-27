"""
A parser/processor to simplify modular docopt cli
"""
import logging
import re
import sys
from textwrap import dedent

import os
from docopt import docopt, DocoptExit, DocoptLanguageError


class DocoptParser:
    """
    A simplified way to implement modular doctopt processors

    Why?
        To make cli implementation a breeze, perhaps even fun.

        doctopt is a great way to specify and parse command line arguments.
        However the developer is left to provide an interpretation and
        implementation of the parsed arguments. The implementation quickly
        becomes a large cascade of if/then/else: a bug feast waiting
        to happen and a maintenance nightmare.

        DocoptParser provides a straight-forward way to implement modular
        commands for processing, using docopt as the command line parser. In
        a nutshell, a command is a Python class that provides a method for
        each action to be performed, thus removing the need for large if/then
        constructs while modularising documentation and implementation of
        subcommands.

    Usage:
        ___doc___ = ''' Usage: pgm.py foo bar [--baz]

        [usage:foo]

        Options:
            -h | --help  this help text

        [options:foo]
        '''
        DocoptParser(__doc__, [FooCommand, ...]).parse().process()

        where FooCommand is

            class FooCommand(DocoptCommand):
                '''
                Usage: pgm.py foo bar [--baz]

                Options:
                    --baz  baz description
                '''
                command = 'foo'
                usage_header = 'Working with foo' # optional
                options_header = 'Options for foo' # optional

                def bar(self):
                    # the bar command, doctopt output is in self.args
                    # to write output, use self.logger, a Python logger
                    # which by default prints to stdout


        Upon the call to .process(), DocoptParser will find and call the
        FooCommmand.bar() method automatically. In bar() use self.args
        to get the parsed arguments as returned by docopt().

        DocoptParser will automatically replace [usage:foo] and [options:foo]
        with the FooCommand.__doc__ string, replacing the latter's Usage:
        with the usage_header and Options: with options_header

        The help text will thus be:

            Usage: pgm.py foo bar [--baz]

            Working with foo
                pgm.py foo bar [--baz]

            Options:
                -h | --help  this help text

            Options for foo
                --baz  baz description

    How to print output in a command:
        You should avoid using print() as it is not really a good way to
        write modular, debuggable code. If your cli is more than a few
        lines of code, it is better to use the built-in logger:

            (...)
            def bar(self):
                self.logger.info('this will go to stdout')

        To change the format of the output, create a logging.Logger and
        set whatever format you like, then use

            logger = ... # your logger setup
            DocoptParser(..., logger=logger)

        To change the loglevel, add --loglevel in options, pass INFO, DEBUG
        or ERROR

    Debugging:
        To debug the parser, set DOCOPT_DEBUG=1. This will print the parsed
        arguments in self.args, along with the command class and method chosen
        for execution on callling parser.process().

        If you don't see debug output despite specifying DOCOPT_DEBUG=1 the
        parser has not been able to parse the arguments and instead prints the
        help text. This means that your arguments don't match any of the
        specified arguments. Make sure that your top-level docstring supports
        all arguments and options.

        The command class is determined by a match to DocoptCommand.command,
        either of and in this order:
            1. a valid literal passed in argv
            2. the value of the <command> tag

        To change the <command> tag to something else, set parser.command_tag:

            parser = DocoptParser(..., command_tag='<dothis>')
    """

    def __init__(self, docs, commands, argv=None, version=None, logger=None,
                 command_tag=None):
        self.docs = docs
        self.commands = commands  # available command implementations
        self.command = None  # chosen command implementation, see get_command
        self.command_tag = command_tag or '<command>'
        self.argv = argv or sys.argv[1:]
        self.version = version
        self.args = None
        self._logger = logger
        self.apply_command_usage()

    @property
    def logger(self):
        if self._logger is None:
            self._logger = setup_console_logger()
            loglevel = self.args.get('--loglevel', 'INFO')
            self._logger.setLevel(loglevel)
        return self._logger

    @property
    def should_debug(self):
        return os.environ.get('DOCOPT_DEBUG')

    def apply_command_usage(self):
        # replace [usage:<command>] [options:<command>] placeholders with command.__doc__
        for command in self.commands:
            if command.__doc__:
                usage, options, description = command.get_command_doc()
                usage_placeholder = '[usage:{}]'.format(command.command)
                options_placeholder = '[options:{}]'.format(command.command)
                descr_placeholder = '[description:{}]'.format(command.command)
                self.docs = self.docs.replace(usage_placeholder, usage)
                self.docs = self.docs.replace(options_placeholder, options)
                self.docs = re.sub(r'\n\s*\n', '\n\n', self.docs)
            if any(v in self.argv for v in ('--help-ext', '-H', '-hh')):
                self.docs = self.docs.replace(descr_placeholder, description)
            else:
                self.docs = self.docs.replace(descr_placeholder, '')

    def parse(self):
        self.args = safe_docopt(self.docs, argv=self.argv, version=self.version)
        self.command = self.get_command()
        if not self.command:
            raise DocoptExit()
        if self.should_debug:
            print("*** docopt parsed args", self.args)
            print("*** docopt using command class {}".format(repr(self.command)))
            print("*** docopt using command method {}".format(repr(self.command.get_command_method())))
        return self

    def get_command(self):
        # find the command
        for commandcls in self.commands:
            global_command = False
            # given as literal
            command_asliteral = self.args.get(commandcls.command)
            # given as <command> arg
            command_asarg = self.args.get(self.command_tag) == commandcls.command
            # catch all?
            if not (command_asliteral or command_asarg):
                global_command = commandcls.command == 'global'
            if command_asliteral or command_asarg or global_command:
                command = commandcls(self.args, argv=self.argv,
                                     logger=self.logger, global_docs=self.docs)
                return command

    def process(self):
        # resolve command and method to call
        assert self.command is not None, "you must call DocoptParser.parse()"
        meth = self.command.get_command_method()
        if meth:
            return meth()


class DocoptCommand:
    """
    Base class for DocoptParser commands

    This assumes either of the following docopt formats:

        pgm.py <command> [<action>]
        pgm.py command action

    How to use:
        1. implement a DocoptCommand subclass for the command you wish to handle
        2. implement methods for each action
        3. to process command without action, implement __call__
        4. Pass your DocoptCommand classes as the command list to DocoptParser

        Each DocoptCommand subclass must at least provide the command name
        and either a valid action method or the __call__ method.

        Each action method, including __call__, is of format
            def action(self):
                # use self.args to get parsed arguments

        If a method with equal name as the action is found, it will be called.
        If no method is found, __call__ will be invoked, which by default raises
        NotImplementedError.

        Note a named <argument> will be used to lookup a method based on the
        value passed. e.g if <argument> is specified as foo then the foo method
        will be found.

        See DocoptParser for a complete example.

    Documentation of commands:
        A command class can have its own docstring in the same format as the
        main docstring, with its own Usage: and Options: sections. If it does
        so, docopt is automatically called on the command's docstring
        and self.args is updated accordingly.

        The command's Usage and Options sections can be included in the main
        docstring by adding [usage:<command>] and [options:<command>]
        placeholders. In this case the Usage: and Options: strings will be
        replaced by usage_header and options_header, respectively.

        See DocoptParser for a complete example.
    """
    command = 'unspecified'
    usage_header = 'Usage of {self.command}'
    options_header = 'Options for {self.command}'
    description_header = 'Working with {self.command}'

    def __init__(self, args, argv=None, logger=None, docs=None,
                 global_docs=None):
        # initialize, if this class contains a __doc__ header
        # with a Usage: section, self.args will automatically
        # be updated accordingly.
        self.args = args
        self.argv = argv
        self.logger = logger
        self.docs = docs or self.__doc__
        self.global_docs = global_docs
        self.parse()

    def parse(self):
        if (self.__doc__ and 'usage:' in self.__doc__.lower() or
                self.__doc__ and 'options:' in self.__doc__.lower()):
            docs = self.add_global_options()
            args = safe_docopt(docs, argv=self.argv)
            self.args.update(args)

    def add_global_options(self):
        # add Options: from top level parser. this is to make sure
        # that global options are checked on any [options] placeholder
        # in this command's docstring
        if self.global_docs and 'Options:' in self.global_docs:
            # get global options as clean as possible
            global_options = self.global_docs.split('Options:', 1)[1]
            global_options = global_options.split('\n')
            docs = dedent(self.docs).split('\n')
            # find options to add, stopping at the first empty line
            # after options. note the first line is always empty
            to_add = []
            for i, opt in enumerate(global_options):
                if i > 0 and not opt:
                    break
                if opt.strip().split('  ')[0] not in self.docs:
                    to_add.append(opt)
            docs.extend(to_add)

            def section(line):
                if line.lower().startswith('options'):
                    line = '\n' + line
                return line

            docs = '\n'.join(section(line) for line in docs)
        else:
            docs = self.docs
        return docs

    def __call__(self):
        raise NotImplementedError

    def get_command_method(self):
        # get the method to call, by default return command itself
        # for <action> style arguments will use the value to lookup
        # the method
        for k, v in self.args.items():
            lookup = str(v if k.startswith('<') else k)
            if v:
                meth = getattr(self, lookup, None)
                if meth is not None:
                    return meth
        return self

    def help(self):
        self.logger.info(dedent(self.__doc__).strip())

    @classmethod
    def get_command_doc(self):
        # return usage, options, description to replace
        # [usage:<command>], [options:<command>], [description:<command>]
        # -- format headers
        usage_header = self.usage_header.format(**locals())
        options_header = self.options_header.format(**locals())
        description_header = self.description_header.format(**locals())
        # get clean sections
        clean_command_doc = dedent(self.__doc__)
        clean_command_doc = clean_command_doc.replace('Usage:', 'usage:')
        clean_command_doc = clean_command_doc.replace('Options:', 'options:')
        clean_command_doc = clean_command_doc.replace('Description:', 'description:')
        # ensure all sections are present
        if 'options:' not in clean_command_doc:
            clean_command_doc += '\noptions:\n'
        if 'description:' not in clean_command_doc:
            clean_command_doc += '\ndescription:\n'
        # split
        usage, options = clean_command_doc.split('options:')
        options, description = options.split('description:')
        # ensure headers are not interfering with top-level
        usage = usage.replace('usage:', usage_header)
        options = (options_header + options) if options.strip() else ''
        description = (description_header + description) if description.strip() else ''
        return usage, options, description


def safe_docopt(doc, argv=None, help=True, version=None, options_first=False):
    try:
        args = docopt(doc, argv=argv, help=help, version=version, options_first=options_first)
    except DocoptLanguageError as e:
        print("*** ERROR {}, check below".format(e))
        print("arguments to doctopt were")
        print("   argv=", argv)
        print("   doc=", doc)
        print("**** ERROR {}, check above messages ***".format(e))
        exit(1)
    return args


def setup_console_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
