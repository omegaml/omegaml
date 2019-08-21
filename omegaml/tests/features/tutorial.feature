Feature: omegaml feature testing

  @connect
  Scenario: connect to omegaml
     Given we have a connection to omegaml
     When we ingest data
     When we build a model
     Then we can predict a result

  @notebook
  Scenario: work with notebook
    Given we have a connection to omegaml
    When we open jupyter
    When we create a notebook
    Then we can list datasets in omegaml

  @nbfolders
  Scenario: create notebook folders
    Given we have a connection to omegaml
    When we open jupyter
    When we create a folder
    Then we can add a notebook in the folder

  @tutorial
  Scenario: omegaml base features tutorial
    Given we have a connection to omegaml
    When we open jupyter
    When we upload the omegaml-tutorial notebook
    When we run the notebook omegaml-tutorial
    Then model iris-model exists

  @tfkeras
  Scenario: tfkeras-tutorial
    Given we have a connection to omegaml
    When we open jupyter
    When we upload the tfkeras-tutorial notebook
    When we run the notebook tfkeras-tutorial
    Then model tfkeras-flower-unfitted exists

  @tfestimator
  Scenario: tfestimator-tutorial
    Given we have a connection to omegaml
    When we open jupyter
    When we upload the tfestimator-tutorial notebook
    When we run the notebook tfestimator-tutorial
    Then model tf-model-mnist-estimator exists
