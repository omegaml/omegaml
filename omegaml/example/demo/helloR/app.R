library(reticulate)
library(jsonlite)

omega_run <- function(om, kwargs) {
   # to restore the omega session do the following
   # if om was passed as "0", this means we're in a local mode, i.e. must import omegaml
   om <- if (om == "0") import("omegaml") else om
   s <- if (is.raw(kwargs)) fromJSON(rawToChar(base64_dec(kwargs))) else kwargs
   s$message <- "hello from R"
   s$scripts <- om$scripts$list()
   return(toJSON(s))
}
