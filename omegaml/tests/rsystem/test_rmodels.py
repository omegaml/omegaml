import os
import unittest
from subprocess import run

from numpy.testing import assert_almost_equal

from omegaml import Omega
from omegaml.backends.rsystem.rmodels import RModelBackend
from omegaml.runtimes.rsystem import rhelper
from omegaml.tests.rsystem.rtestutil import r_source
from omegaml.tests.util import OmegaTestMixin


@unittest.skipUnless(rhelper() is None, "results consolidated as RSystemTestCase.test_inside_r result")
class RSystemTester(OmegaTestMixin, unittest.TestCase):
    """ run reticulated tests (python within R)
    """
    def setUp(self):
        # force test mode for omega run from R
        os.environ['OMEGA_TEST_MODE'] = "yes"

    def test_inside_r(self):
        """ run R runtime tests

        this launches RScript to effectively run R_unittests
        """
        from omegaml.runtimes import rsystem
        appdir = os.path.dirname(rsystem.__file__)
        rcmd = fr'Rscript -e source("{appdir}/unittest.R")'
        output = run(rcmd.split(' '), capture_output=True)
        messages = output.stderr.decode('utf8')
        output = output.stdout.decode('utf8')
        self.assertTrue("FAILED" not in messages,
                        f"R tests failed, results below\n{messages}")
        print(f"R tests OK: {messages}")
        print(f"R tests output: {output}")


@unittest.skipUnless(rhelper() is not None, "results consolidated as RSystemTestCase.test_inside_r result")
class RSystemModelTests(OmegaTestMixin, unittest.TestCase):
    """ test R functionality by running inside R session

    How this works

        If run within native Python unittest, the tests are skipped.
        When run within R reticulated Python session, the tests are executed.
        The actual test launch is by the RSystemTester.test_inside_r test case.

    Rationale

        This way we can write omegaml tests for the R backend that are very
        similar to the omegaml tests for native Python frameworks. A case could
        be made to externalize testing of the R backend, which would be the
        path if we decide to provide a separate R package.
    """

    def setUp(self):
        om = self.om = Omega()
        om.scripts.register_backend(RModelBackend.KIND, RModelBackend)
        self.clean()

    def test_r_model_native(self):
        """ store and use models from within r"""
        om = self.om
        r_source("""
        library(caret)
        data(mtcars)
        model <- train(mpg ~ wt,
                       data = mtcars,
                      method = "lm")
        predict(model, mtcars)
        om$models$put('r$model', 'mtcars-model')
        om$datasets$put(mtcars, 'mtcars')
        """)
        self.assertIn('mtcars-model', om.models.list())
        self.assertIn('mtcars', om.datasets.list())
        # use native R predict
        r_source("""
        model_ <- om$models$get('mtcars-model')
        mtcars_ <- om$datasets$get('mtcars')
        yhat <- predict(rmodel(model_), mtcars_)
        om$datasets$put(yhat, 'mtcars-yhat')
        """)
        self.assertIn('mtcars-yhat', om.datasets.list())
        data = om.datasets.get('mtcars-yhat')
        expected = [[23.282610646808614, 21.91977039576433, 24.88595211862542,
                                    20.10265006103862, 18.900143957176017, 18.793254525721565,
                                    18.20536265272207, 20.236261850356687, 20.450040713265594,
                                    18.900143957176017, 18.900143957176017, 15.533126866360728,
                                    17.35024720108644, 17.08302362245031, 9.226650410547972,
                                    8.296712356894222, 8.718925611139316, 25.527288707352135,
                                    28.653804577394904, 27.478020831395916, 24.111003740580628,
                                    18.472586231358203, 18.92686631503963, 16.762355328086947,
                                    16.73563297022333, 26.94357367412365, 25.8479570017155,
                                    29.198940677812615, 20.34315128181114, 22.48093991090021,
                                    18.20536265272207, 22.427495195172988]]
        assert_almost_equal(data, expected)
        # use RModelProxy.predict
        r_source("""
                model_ <- om$models$get('mtcars-model')
                mtcars_ <- om$datasets$get('mtcars')
                yhat <- model_$predict('mtcars')
                om$datasets$put(yhat, 'mtcars-yhat2')
                """)
        self.assertIn('mtcars-yhat2', om.datasets.list())
        data = om.datasets.get('mtcars-yhat2')
        expected = [[23.282610646808614, 21.91977039576433, 24.88595211862542,
                     20.10265006103862, 18.900143957176017, 18.793254525721565,
                     18.20536265272207, 20.236261850356687, 20.450040713265594,
                     18.900143957176017, 18.900143957176017, 15.533126866360728,
                     17.35024720108644, 17.08302362245031, 9.226650410547972,
                     8.296712356894222, 8.718925611139316, 25.527288707352135,
                     28.653804577394904, 27.478020831395916, 24.111003740580628,
                     18.472586231358203, 18.92686631503963, 16.762355328086947,
                     16.73563297022333, 26.94357367412365, 25.8479570017155,
                     29.198940677812615, 20.34315128181114, 22.48093991090021,
                     18.20536265272207, 22.427495195172988]]
        assert_almost_equal(data, expected)


    def test_r_model_py(self):
        """ store model from r, use from within python """
        om = self.om
        r_source("""
        library(caret)
        data(mtcars)
        model <- train(mpg ~ wt,
                       data = mtcars,
                      method = "lm")
        predict(model, mtcars)
        om$models$put('r$model', 'mtcars-model')
        om$datasets$put(mtcars, 'mtcars')
        """)
        model = om.models.get('mtcars-model')
        # note we pass the dataset name because the model is picky about the data type it receives
        yhat = model.predict('mtcars')
        assert_almost_equal(yhat, [23.282610646808614, 21.91977039576433, 24.88595211862542,
                                    20.10265006103862, 18.900143957176017, 18.793254525721565,
                                    18.20536265272207, 20.236261850356687, 20.450040713265594,
                                    18.900143957176017, 18.900143957176017, 15.533126866360728,
                                    17.35024720108644, 17.08302362245031, 9.226650410547972,
                                    8.296712356894222, 8.718925611139316, 25.527288707352135,
                                    28.653804577394904, 27.478020831395916, 24.111003740580628,
                                    18.472586231358203, 18.92686631503963, 16.762355328086947,
                                    16.73563297022333, 26.94357367412365, 25.8479570017155,
                                    29.198940677812615, 20.34315128181114, 22.48093991090021,
                                    18.20536265272207, 22.427495195172988]
                            )

    def test_r_model_runtime(self):
        """ store model from r, use from runtime """
        om = self.om
        r_source("""
        library(caret)
        data(mtcars)
        model <- train(mpg ~ wt,
                       data = mtcars,
                      method = "lm")
        predict(model, mtcars)
        om$models$put('r$model', 'mtcars-model')
        om$datasets$put(mtcars, 'mtcars')
        """)
        yhat = om.runtime.model('mtcars-model').predict('mtcars').get()
        assert_almost_equal(yhat, [23.282610646808614, 21.91977039576433, 24.88595211862542,
                                   20.10265006103862, 18.900143957176017, 18.793254525721565,
                                   18.20536265272207, 20.236261850356687, 20.450040713265594,
                                   18.900143957176017, 18.900143957176017, 15.533126866360728,
                                   17.35024720108644, 17.08302362245031, 9.226650410547972,
                                   8.296712356894222, 8.718925611139316, 25.527288707352135,
                                   28.653804577394904, 27.478020831395916, 24.111003740580628,
                                   18.472586231358203, 18.92686631503963, 16.762355328086947,
                                   16.73563297022333, 26.94357367412365, 25.8479570017155,
                                   29.198940677812615, 20.34315128181114, 22.48093991090021,
                                   18.20536265272207, 22.427495195172988])
