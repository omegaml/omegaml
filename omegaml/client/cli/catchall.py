from omegaml.client.docoptparser import DocoptCommand


class GlobalCommand(DocoptCommand):
    """
    Usage: om <command> [<action>] [<args> ...] [options]
           om (models|datasets|scripts|jobs) [<args> ...] [--raw] [options]
           om runtime [<args> ...] [--async] [options]
           om cloud [<args> ...] [options]
           om [-h] [-hh] [--version] [--copyright]
    """
    command = "global"

    def __call__(self):
        if self.args.get('--copyright'):
            logger = self.logger
            logger.info("(c) omega|ml by one2seven GmbH, Zurich, Switzerland, https://omegaml.io")
            logger.info("third party components (c) by their respective copyright holders")
            logger.info("see LICENSE and THIRDPARTY-LICENSES at https://github.com/omegaml/omegaml/")
            return
        self.help()

