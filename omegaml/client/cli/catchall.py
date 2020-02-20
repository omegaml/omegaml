from omegaml.client.docoptparser import CommandBase


class CatchallCommandBase(CommandBase):
    command = "catchall"

    def __call__(self):
        if self.args.get('--copyright'):
            logger = self.logger
            logger.info("(c) omega|ml by one2seven GmbH, Zurich, Switzerland, https://omegaml.io")
            logger.info("third party components (c) by their respective copyright holders")
            logger.info("see LICENSE and THIRDPARTY-LICENSES at https://github.com/omegaml/omegaml/")
            return
        self.parser.help()
