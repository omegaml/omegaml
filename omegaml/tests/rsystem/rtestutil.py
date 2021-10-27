from unittest import TestSuite, TestLoader, TextTestRunner

# list all test cases to be called from within reticulated python
from omegaml.runtimes.rsystem import rhelper
from omegaml.util import temp_filename, remove_temp_filename

RE_TEST_CASES = [
    'omegaml.tests.rsystem.test_rmodels.RSystemModelTests',
]


def R_unittests():
    # -- build test suite, adopted from https://docs.python.org/3/library/unittest.html#load-tests-protocol
    suite = TestSuite()
    loader = TestLoader()
    runner = TextTestRunner()
    tests = loader.loadTestsFromNames(RE_TEST_CASES)
    suite.addTests(tests)
    # -- run the suite
    #    this will print any failures in stderr
    runner.run(suite)


def r_source(r_code):
    """ helper to source given r code and reticulated r session

    Args:
            r_code (str): the string of R code, as entered in REPL or R file
    """
    r = rhelper()
    fn = temp_filename(ext='R')
    with open(fn, 'w') as fout:
        fout.write(r_code)
    result = r.source(fn)
    remove_temp_filename(fn)
    return result
