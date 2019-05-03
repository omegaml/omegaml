Feature: omegaml feature testing

  Scenario: connect to omegaml
     Given we have a connection to omegaml
     When we ingest data
     When we build a model
     Then we can predict a result