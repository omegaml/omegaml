"""
A parser/processor to simplify modular docopt cli
"""
from getpass import getpass

import inspect
import logging
import os
import re
import sys
from docopt import docopt, DocoptExit, DocoptLanguageError
from textwrap import dedent


class CommandParser:
    """
    A pythonic, declarative and modular approach to cli (based on docopt)

    Why?
        To make cli implementation a breeze, perhaps even fun: No more untestable
        if/then mess. Every command is a class, every action is a method.

    Tell me more!
        CommandParser provides a straight-forward way to implement a modular
        cli, using docopt as the command line parser. In a nutshell,
        a Command is a Python class that provides a method for each action
        to be performed, thus greatly reducing the need for if/then constructs
        while modularising documentation and implementation of subcommands.

    Why not use docopt directly?
        doctopt is a great way to specify and parse command line arguments
        and CommandParser uses it as the actual parser. With docopt however
        the developer is left to provide an interpretation and implementation
        of the parsed arguments. The implementation quickly becomes a large
        cascade of if/then/else: a bug feast waiting to happen and a
        maintenance nightmare. Also hard to write unit tests. Note that's not
        the fault of docopt, it's does what it does flawlessly. CommandParser
        provides the missing link from docopt's parsing to implementation.


    Usage:
        # pgm.py
        ___doc___ = '''Usage: pgm.py foo bar [--baz]
                                     foo bax [--pox]

        [usage:foo]

        Options:
            -h | --help  this help text

        [options:foo]
        '''
        CommandParser(__doc__, [FooCommand, ...]).parse().process()
        # that's it, notice there are no if/then cascades
        # end of pgm.py

        where FooCommand is

            # foo.py
            class FooCommand(CommandBase):
                '''
                Usage: pgm.py foo bar [--baz]

                Options:
                    --baz  baz description
                '''
                command = 'foo'
                usage_header = 'Working with foo' # optional
                options_header = 'Options for foo' # optional

                def bar(self):
                    # the bar command, docopt output is in self.args
                    # as parsed to the docstring of foo.py. If you want
                    # self.args of pgm.py, access self.parser.args
                    #
                    # to write output, use self.logger, a Python logger
                    # which by default prints to stdout
                    ... your code ...
                    baz = self.args.get('--baz')
                    self.logger.info(f"Hello {baz}")

                def bax(self):
                    # the bax command ...
                    pox = self.args.get('--pox')
                    self.logger.info(f"Welcome {pox}")

                # notice the absence of if/then. every action is a method
            # -- end of foo.py

        Upon the call to .process(), CommandParser will find and call the
        FooCommmand.bar() method automatically. In bar() use self.args
        to get the parsed arguments as returned by docopt(FooCommand.__doc__).

        CommandParser will automatically replace [usage:foo] and [options:foo]
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

    How to implement help:
        CommandParser automatically handles -h, --help and prog help <action>
        -h prints only the usage section, --help and prog help will print all sections

        If a command is given (e.g. prog foo -h) it will print the usage or help
        of the command.

        To override what is printed for help, implement the Command.help() method.

            # FooCommand
            def help(self, usage_only=True):
                ...

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
            CommandParser(..., logger=logger)

        To change the loglevel, add --loglevel in options, pass INFO, DEBUG
        or ERROR


    Optional Description tag:
        For the top level module and each command you can add more descriptions
        that only get printed on prog help or prog help <action>

        # pgm.py
        (...)

        Description:
            lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum
            lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum

        [description:foo]

        # foo.py
        '''
        (...)

        Description:
            lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum
            lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum
        '''

        The help text will thus be:

            Usage: pgm.py foo bar [--baz]

            Working with foo
                pgm.py foo bar [--baz]

            Options:
                -h | --help  this help text

            Options for foo
                --baz  baz description

            Description for foo
                lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum
                lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum lorem ipsum


    My Command's parameters are not recognized:
        Before a command's docopts are parsed, the top-level docopt must parse.
        Thus if you do something like this, your command will never receive
        a call:

        # pgm.py
        '''
        Usage: pgm foo
        '''

        # foo.py
        '''
        Usage: pgm foo [--baz]
        '''

        To make it work, add [options:foo] to pgm.py, and either

        (a) add an Options: section in foo.py that includes --baz,
        (b) or include [--baz] as a global option

        Note the effect of (a) and (b) is effectively the same, as every
        command's options section is added to the global Options: if
        there is a corresponding [foo:<command>] placeholder.

    Options are not parsed:
        If you have applied Options either at the top-level or a sub command
        and still find the parser does not accept it, make sure that your
        command includes the [options] parameter. Otherwise the parser may
        not recognize the option.

        E.g. the following will not work:

        # pgm.py
        '''
        Usage:
            pgm foo --baz

        Options:
            --baz    some flag
        '''

        # foo.py
        '''
        Usage:
            pgm foo
        '''

        To make it work, add [options] to the pgm foo statement in foo.py:

        # foo.py
        '''
        Usage:
            pgm foo [options]
        '''

        Now the parser will accept the --baz option.

    Debugging:
        To debug the parser, set DOCOPT_DEBUG=1. This will print the parsed
        arguments in self.args, along with the command class and method chosen
        for execution on callling parser.process().

        If you don't see debug output despite specifying DOCOPT_DEBUG=1 the
        parser has not been able to parse the arguments and instead prints the
        help text. This means that your argv don't match any of the
        specified docopts. Make sure that your top-level docstring supports
        all arguments and options.

        The command class is determined by a match to CommandBase.command,
        in this order:
            1. a valid literal passed in argv
            2. the value of the <command> tag

        The method called on the command class is determined in this order:
            3. a valid literal passed in argv
            4. the value of the <action> tag
            5. __call__()

        For example, if you specify (1) or (2)

            (1)
            pgm.py foo bar

            (2)
            pgm.py <command> <action>

        (1) argv = "pgm.py foo bar" => if there is FooCommand.command == 'foo', the
            "foo" part is a literal match. The "bar" part is also a literal match.

        (2) argv = "pgm.py foo bar" => if there is FooCommand.command == 'foo', the
            "foo" part is a match by the <command> tag. The "bar" part is a match
            by the "<action>" tag. It is translated to the corresponding method of
            the same name if it exists, or reverts to FooCommand.__call()

        In both (1) and (2) the "bar" part is translated to calling FooCommand.bar()
        if it exists, else reverts to FooCommand.__call_().

        The default command tag is '<command>', change by setting CommandParser.command_tag
        to something else:

            parser = CommandParser(..., command_tag='<dothis>')

        The default action tag is '<action>'. Change by setting the Command.action_tag
        to something else.

            class FooCommand(BaseCommand):
                action_tag = '<dothis>'
                ...

    """

    def __init__(self, docs, commands, argv=None, version=None, logger=None,
                 command_tag=None, catchall='catchall', askfn=None):
        self.docs = docs
        self.commands = commands  # available command implementations
        self.command = None  # chosen command implementation, see parse_command
        self.command_tag = command_tag or '<command>'
        self.argv = argv or sys.argv[1:]
        self.version = version
        self.args = None
        self.catchall = catchall
        self._logger = logger
        self._askfn = askfn
        self.apply_command_usage()

    @property
    def logger(self):
        """
        return the logger instance, defaults to the console logger

        Returns:
            a logger, any command instance should use this logger for output
            this helps not only output control but also testing.
        """
        if self._logger is None:
            self._logger = setup_console_logger()
            loglevel = self.args.get('--loglevel', 'INFO')
            self._logger.setLevel(loglevel)
        return self._logger

    @property
    def should_debug(self):
        return os.environ.get('DOCOPT_DEBUG')

    @property
    def silent(self):
        return self.args.get('-q') or self.args.get('--noinput')

    def apply_command_usage(self):
        """
        For every command add usage, options and descriptions to global docs

        This works by extracting the usage, options and descriptions from
        the doc string of every registered command class and adding these
        to the global docs by replacing the corresponding [usage:<command>],
        [options:<command>] and [descriptions:<command] sections, respectively.

        Returns:
            None
        """
        # replace [usage:<command>] [options:<command>] placeholders with command.__doc__
        for command in self.commands:
            if command.__doc__:
                usage, options, description = command.get_command_docparts()
                usage_placeholder = '[usage:{}]'.format(command.command)
                options_placeholder = '[options:{}]'.format(command.command)
                descr_placeholder = '[description:{}]'.format(command.command)
                self.docs = self.docs.replace(usage_placeholder, usage)
                self.docs = self.docs.replace(options_placeholder, options)
                self.docs = re.sub(r'\n\s*\n', '\n\n', self.docs)
                if any(v in self.argv for v in ('--help-ext', '-H', '-hh', 'help')):
                    self.docs = self.docs.replace(descr_placeholder, description)
                else:
                    self.docs = self.docs.replace(descr_placeholder, '')

    def parse(self):
        """
        Parse the doc string given on instantiation, determine current command

        Returns:
            the parser self
        """
        try:
            self.args = safe_docopt(self.docs, argv=self.argv, version=self.version, help=False)
        except DocoptExit as e:
            if self.should_debug:
                # see
                left = inspect.trace()[-1][0].f_locals.get('left')
                print(
                    "*** DocoptExit indicates that your command was not parsed. Did you add [options] to the command?")
                print(f"*** The following arguments were not parsed: {left}")
                raise e
            # by specifying docopt(help=False) we get to control what happens on parse failure
            if self.argv:
                # if help requested, show help. this simulates a valid Usage: help <action>
                if self.argv[0] in ('help', '--help'):
                    action = self.argv[1] if len(self.argv) > 1 else None
                    self.args = {
                        '<command>': 'help',
                        '<action>': action,
                    }
                    self.help(usage_only=False)
                    # raise SystemExit because
                    raise SystemExit
                # custom handling should be provided by a Command with command='catchall'
                elif self.argv[0] == '--copyright':
                    self.args = {
                        '--copyright': True,
                    }
                else:
                    # this re-raises DocoptExit which prints usage
                    raise
            else:
                # this re-raises DocoptExit which prints usage
                raise
        # if we get here it means docopt has decided all the arguments are valid
        # -- see if we have a command
        try:
            self.command = self.parse_command()
            # -- no command?!
            if not self.command:
                self.help()
                raise DocoptExit()
        except DocoptExit as e:
            if self.should_debug:
                # see
                left = inspect.trace()[-1][0].f_locals.get('left')
                print(
                    "*** DocoptExit indicates that your command was not parsed. Did you add [options] to the command?")
                print(f"*** The following arguments were not parsed: {left}")
            raise e
        if self.should_debug:
            print("*** docopt parsed args", self.args)
            print("*** docopt using command class {}".format(repr(self.command)))
            print("*** docopt using command method {}".format(repr(self.command.get_command_method())))
        return self

    def parse_command(self):
        """
        Instantiate the command requested

        The command requested is determined by considering
            * a literal as specified
            * a <command> placeholder
            * neither literal nor <command>, the 'catchall' command, if present

        Returns:
            the command class or None
        """
        for commandcls in self.commands:
            is_global_command = False
            # given as literal
            command_asliteral = self.args.get(commandcls.command)
            # given as <command> arg
            command_asarg = self.args.get(self.command_tag) == commandcls.command
            # catch all?
            if not (command_asliteral or command_asarg):
                is_global_command = commandcls.command == self.catchall
            if command_asliteral or command_asarg or is_global_command:
                command = self._command_instance(commandcls)
                command.parse()
                return command
        self.help()

    def _command_instance(self, commandcls):
        # instantiate the commandcls given current arguments and a parsed global instance
        command = commandcls(commandcls.__doc__, argv=self.argv,
                             logger=self.logger, parser=self)
        return command

    def process(self):
        """
        Process the command as identified in parse

        Processing means to find the <action> method to call on the command class,
        see get_command_method() for details

        Returns:

        """
        assert self.command is not None, "you must call CommandParser.parse()"
        meth = self.command.get_command_method()
        if meth:
            return meth()

    def help(self, usage_only=True):
        """
        show default help

        This assumes that the docs contain any of the following Usage patterns:

            Usage:
                prog <command> <action>
                prog help <a-command>

        Either of the following is shown, in this order:
            - if the command was 'help', but no <a-command> was given, show
              self.docs
            - if <a-command> was given this is used to lookup the actual command,
              then calls command.help()
            - if <command> was not 'help', i.e. we got here by some command
              calling parser.help(), we show usage information by calling the
              command's command.help(usage_only=True)
            - if no command can be identified, we let the user know we don't
              know what to do. If possible we hint at the closest command that
              is similar to the requested <command> or help <a-command>

        This is called after the following has already happened:
            - docopt has decided argv was valid as given by specs
            - no command was found, or the command did not identify a method
            - if none of the above, the command called parser.help()

        Raises:
            ValueError(message + hint) if no command was found
        """
        command_requested = self.args.get(self.command_tag)
        help_requested = command_requested == 'help' or self.args.get('help')
        action_requested = self.args.get('<any-command>')
        closest_command = None
        # if help was actually requested, see if we can find a command
        if help_requested:
            if not action_requested:
                docs = self.docs
                self.logger.info(dedent(docs).strip())
                return
            command_requested = action_requested
            usage_only = False
        for commandcls in self.commands:
            if commandcls.command == command_requested:
                command = self._command_instance(commandcls)
                return command.help(usage_only=usage_only)
            if command_requested in commandcls.command or commandcls.command in command_requested:
                closest_command = commandcls.command
        hint = f"try: om help {closest_command}" if closest_command else 'try: om -h'
        msg = f"sorry, I don't know about >{command_requested}<. {hint}"
        raise SystemExit(msg)

    def ask(self, prompt, hide=False, options=None, default=None):
        """
        ask user input

        Can be overridden by providing CommandParser(..., askfn=callable), e.g.
        for testing purpose

        Args:
            prompt (str): the prompt text
            hide (bool): if True don't ask, just return default
            options (str): options string, if provided answer will be checked
                to be in options (lowercase)
            default (str): the default answer if no answer given or self.silent
                is active (-q switch)

        Returns:
            answer as str
        """
        value = default
        if self._askfn:
            return self._askfn(prompt, hide=hide, options=options, default=default,
                               parser=self)
        if not self.silent:
            options_text = f'[{options}] ' if options else ''
            prompt = f'{prompt} {options_text}'
            if hide:
                value = getpass(prompt=prompt)
            else:
                value = input(prompt)
            if not value and default:
                return default
            if options:
                assert value.lower() in options.lower()
        return value


class CommandBase:
    """
    Base class for CommandParser commands

    This assumes either of the following docopt formats:

        pgm.py <command> [<action>]
        pgm.py command action

    How to use:
        1. implement a CommandBase subclass for the command you wish to handle
        2. implement methods for each action (e.g. action <dothis> gets method dothis)
        3. to process command without action, implement __call__
        4. Pass your CommandBase classes as the command list to CommandParser

        Each CommandBase subclass must at least provide the command name
        and either a valid action method or the __call__ method.

        Each action method, including __call__, is of format
            def action(self):
                # use self.args to get parsed arguments

        If a method with equal name as the action is found, it will be called.
        If no method is found, __call__ will be invoked, which by default prints
        the command's help

        Note a named <argument> will be used to lookup a method based on the
        value passed. e.g if <argument> is specified as foo then the foo method
        will be found.

        See CommandParser for a complete example.

    Documentation of commands:
        A command class can have its own docstring in the same format as the
        main docstring, with its own Usage: and Options: sections. If it does
        so, docopt is automatically called on the command's docstring
        and self.args is updated accordingly.

        The command's Usage and Options sections can be included in the main
        docstring by adding [usage:<command>] and [options:<command>]
        placeholders. In this case the Usage: and Options: strings will be
        replaced by usage_header and options_header, respectively.

        See CommandParser for a complete example.
    """
    command = 'unspecified'
    action_tag = '<action>'
    usage_header = 'Usage of {self.command}'
    options_header = 'Options for {self.command}'
    description_header = 'Working with {self.command}'
    options_label = 'Options:'

    def __init__(self, docs, argv=None, logger=None, parser=None):
        # initialize, if this class contains a __doc__ header
        # with a Usage: section, self.args will automatically
        # be updated accordingly.
        self.argv = argv or sys.argv[1:]
        self.logger = logger
        self.docs = docs or self.__doc__
        self.parser = parser
        self.global_docs = self.parser.docs if self.parser else None
        self.args = {}

    def parse(self):
        """
        Use docopt on self.docs and self.args

        If this method returns, self.args will contain the parsed options
        as given in self.docs
        """
        if self.docs is None:
            return
        docs = self.add_global_options() if self.global_docs else self.docs
        args = safe_docopt(docs, argv=self.argv, help=False)
        self.args.update(args)
        if self.parser.should_debug:
            print("*** {self.command} parsed args".format(**locals()), self.args)

    @property
    def has_usage(self):
        return self.docs and 'usage:' in self.__doc__.lower()

    @property
    def has_description(self):
        return self.docs and 'description:' in self.__doc__.lower()

    @property
    def usage(self):
        lines = []
        for line in self.docs.split('\n'):
            if any(v in line.lower() for v in ('options:', 'description:')):
                break
            lines.append(line)
        return '\n'.join(lines)

    @property
    def silent(self):
        return self.parser.silent

    def add_global_options(self):
        # add Options: from top level parser. this is to make sure
        # that global options are checked on any [options] placeholder
        # in this command's docstring
        if self.global_docs and 'options:' in self.global_docs.lower():
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
            # extend local options with global options
            if self.options_label in docs:
                pos_options = docs.index(self.options_label) + 1
                docs[pos_options:pos_options] = to_add
            else:
                docs.extend(to_add)

            def section(line):
                section_headers = 'options', 'description'
                if any(line.lower().startswith(v) for v in section_headers):
                    line = '\n' + line
                return line

            docs = '\n'.join(section(line) for line in docs)
        else:
            docs = self.docs
        return docs

    def help(self, usage_only=False):
        """
        Display command's help

        This is called by the parser upon the help command, and if __call__
        is not implemented.

        Args:
            usage_only (bool): if True, show only usage, else show full docs

        Returns:

        """
        if usage_only:
            self.logger.info(dedent(self.usage))
        else:
            self.logger.info(dedent(self.docs))

    def __call__(self):
        """
        If no method was found, this is what gets help. By
        default we call self.help(usage_only=True) to show
        usage information
        """
        self.help(usage_only=True)

    def get_command_method(self):
        """
        get the method to call, by default return command itself

        for <action> style arguments will use the value to lookup.
        The action tag used for the lookup is self.action_tag

        Returns:
              the method or self if none was found. Returning self
              means __call__() will be called
        """
        #
        #
        #
        for k, v in self.args.items():
            lookup = str(v if k == self.action_tag else k)
            if v:
                meth = getattr(self, lookup, None)
                if meth is not None:
                    return meth
        return self

    @classmethod
    def get_command_docparts(self):
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
            # ensure options is before description
            if 'description:' in clean_command_doc:
                before, after = clean_command_doc.split('description:')
                before += '\noptions:\n'
                clean_command_doc = before + 'description:' + after
            else:
                clean_command_doc += '\noptions:\n'
        if 'description:' not in clean_command_doc:
            clean_command_doc += '\ndescription:\n'
        # split
        try:
            usage, options = clean_command_doc.split('options:')
            options, description = options.split('description:')
        except:
            raise ValueError(f"cannot parse {clean_command_doc}")
        # ensure headers are not interfering with top-level
        usage = usage.replace('usage:', usage_header)
        options = (options_header + options) if options.strip() else ''
        description = (description_header + description) if description.strip() else ''
        return usage, options, description

    def parse_kwargs(self, argname, resolve_bool=True, splitby=None,
                     pyeval=False, literal_escape=None,
                     **defaults):
        """
        Parse [<kw=value>] and [<kw=value>...] kind arguments

        Usage:
            Positional parameters

                prog [<kw=value>]
                prog [<kw=value>...]

            => in your BaseCommand call self.parse_kwargs('<kw=value>') to get back the parsed dict

            Long (named) parameters

                prog [--param=<kw=value>]
                prog [--param=<kw=value>]...

            => in your BaseCommand call self.parse_kwargs('--param') to get back the parsed dict

        Examples:
                a=1    => { a: '1' }
                a=1    => { a: 1 } # assuming pyeval=True
                a=yes  => { a: True }
                a=false => { a: False }
                a=*false => { a: 'false' }
                a=[0,1,2] => { a: [0,1,2] } # assuming pyeval=True
                a=1,2,3   => { a: ['1', '2', '3'] # assuming splitby=', pyeval=False

        Args:
            argname (str): the name of the argument as specified in docopt
            splitby (str): specify string to split values by, by default splits on comma,
                unless pyeval is given. If pyeval is True by default does not split
            resolve_bool (bool): resolve yes/true => True, no/false => False (defaults to True)
            pyeval (bool): eval() the final value, defaults to False, can also be a callable
            literal_escape (str): the escape char to keep yes/true, no/false, defaults to *
                if resolve_bool is True, else no literal escape
            **defaults (dict): any defaults

        Returns:
            dict of kw => value, can contain a single or multiple items
        """
        # replace literal *yes, *no with 'yes', 'no'
        # replace literal *true, *false with 'true', 'false'
        # replace yes/true with True
        # replace no/false with False
        # split values that contain a comma to a list
        splitby = None if pyeval else ','
        literal_escape = '*' if not resolve_bool else None
        values = self.args.get(argname)
        if values is None:
            return {}
        if not isinstance(values, list):
            values = [values]  # allow single values
        # seperate method to make it reusable by parse_kwargs and parse_kwarg
        BOOLMAP = {'true': True, 'yes': True,
                   'no': False, 'false': False,
                   'y': True, 'n': False}
        doeval = lambda v: pyeval(v) if callable(pyeval) else (eval(v) if pyeval else v)
        split = lambda v: ([v for v in v.split(splitby) if v]
                           if splitby and (len(v) > 1 and splitby in v)
                           else v)
        literal = lambda v: v.replace(literal_escape, '') if literal_escape else v
        truefalse = lambda v: BOOLMAP.get(v.lower()) if resolve_bool else v
        resolve = lambda v: truefalse(v) if resolve_bool and v in BOOLMAP else doeval(split(literal(v)))
        requested_kwargs = {k: resolve(v) for arg in values for k, v in [arg.split('=', 1)]}
        real_kwargs = {}
        real_kwargs.update(defaults)
        real_kwargs.update(requested_kwargs)
        return real_kwargs

    def ask(self, *args, **kwargs):
        return self.parser.ask(*args, **kwargs)


def safe_docopt(doc, argv=None, help=True, version=None, options_first=False):
    """
    A docopt drop-in replacement to print meaning full error messages in case
    of a DocoptLanguageError exception

    Args:
        same as docopt

    Returns
        parsed args
    """
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
    """
    Set up a default console logger that prints messages as is

    Returns:
        the logger instance
    """
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
