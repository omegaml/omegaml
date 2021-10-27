library(reticulate)

OmegaEnv = new.env()

rmodel <- function(name) {
    get(name$key, envir = OmegaEnv)
}

om_save_model <- function(name, fn) {
    saveRDS(get(name), fn)
}

om_load_model <- function(fn, key) {
    model = readRDS(fn)
    assign(key, model, envir = OmegaEnv)
    key
}

om_model_predict <- function(pymodel, XName) {
    model = rmodel(pymodel)
    data <- om$datasets$get(XName)
    predict(model, data)
}

om_model_predict_py <- function(pymodel, X) {
    model = rmodel(pymodel)
    predict(model, X)
}

