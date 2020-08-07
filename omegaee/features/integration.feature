Feature: cloud integration

  @apitest
  Scenario: api sign up a new user
    Given we have the site deployed
    Given we are not logged in
    When we signup a new user (api)
    Then the site sends out a registration email
    Then we confirm the account
    Then we log out
    Then the service is deployed (api)