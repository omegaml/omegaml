Feature: omegaml feature testing

  Scenario: connect to omegaml
     Given we have a connection to omegaml
     When we ingest data
     When we build a model
     Then we can predict a result

  Scenario: work with notebook
    Given we have a connection to omegaml
    When we open jupyter
    When we create a notebook
    Then we can list datasets in omegaml

  Scenario: create notebook folders
    Given we have a connection to omegaml
    When we open jupyter
    When we create a folder
    Then we can add a notebook in the folder
