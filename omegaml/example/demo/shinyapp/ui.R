library(shiny)
ui <- fluidPage(
  titlePanel("Example shiny app"),
  sidebarLayout(
    sidebarPanel(
      sliderInput(inputId = "bins", label = "Number of bins:",
                  min = 1, max = 50, value = 30)
    ),
    mainPanel(
      plotOutput(outputId = "distPlot")
    )
  )
)
