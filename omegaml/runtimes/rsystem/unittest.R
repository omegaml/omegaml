# helper RScript startup to run omegaml unit tests for rsystem backend
library(reticulate)

print("starting unittest for omegaml inside R")
omtests <- import("omegaml.tests")
om <- import("omegaml")
omtests$rsystem$rtestutil$R_unittests()
