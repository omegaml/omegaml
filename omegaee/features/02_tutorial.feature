Feature: Tutorial

  @always
  Scenario: sign up a new user
    Given we have the site deployed
    Given we are not logged in
    When we signup a new user
    Then the site sends out a registration email
    Then we confirm the account
    Then we log out

  @quickstart
  Scenario: omegaml base features tutorial
    Given we are not logged in
    When we log in
    Then the site shows the dashboard
    Given we have a connection to omegaml-ee
    When we login to jupyter notebook
    When we upload the quickstart notebook
    When we run the notebook quickstart
    Then model mymodel exists

  @tutorial
  Scenario: omegaml base features tutorial
    Given we are not logged in
    When we log in
    Then the site shows the dashboard
    Given we have a connection to omegaml-ee
    When we login to jupyter notebook
    When we upload the omegaml-tutorial notebook
    When we run the notebook omegaml-tutorial
    Then model iris-model exists

  @apphub
  Scenario: deploy dash app
    Given we are not logged in
    When we log in
    Then the site shows the dashboard
    Given we have a connection to omegaml-ee
    When we deploy app ../omegaml-apps/helloworld as apps/helloworld
    Then we can access the app at /apps/{user}/helloworld



