Feature: signup a new user

    Scenario: sign up a new user
       Given we have the site deployed
       When we signup a new user
       Then the site sends out a registration email


    Scenario: login the new user
        Given we have a new user
        When we log in
        Then the site shows the dashboard
