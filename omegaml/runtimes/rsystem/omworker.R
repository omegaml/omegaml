library(reticulate)
om <- import("omegaml")

om_runtime_worker <- function() {
    om$runtimes$rsystem$load()
    om$runtimes$rsystem$start_worker(om)
}

om_runtime_worker()
