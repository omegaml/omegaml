Feature: signup a new user

    Scenario: sign up a new user
       Given we have the site deployed
       When we signup a new user
       Then the site sends out a registration email
       Then we confirm the account
       Then we log out
       
    Scenario: login the new user
        Given we are not logged in
        When we log in
        Then the site shows the dashboard
        Then we can get an omega instance
        Then we log out

    Scenario: login to the notebook
        Given we are not logged in
        When we log in
        Then the site shows the dashboard
        Then we can load the jupyter notebook
        Then we log out


