![Github Actions](https://github.com/platzky/platzky/actions/workflows/tests.yml/badge.svg?event=push&branch=main)
[![Coverage Status](https://coveralls.io/repos/github/platzky/platzky/badge.svg?branch=main)](https://coveralls.io/github/platzky/platzky?branch=main)

# platzky

Blog engine in python 

## Configuration

For details check `config.yml.tpl` file.


# API
`platzky.config.from_file(path_to_config)` - creates _platzky_ config from file (see __config.yml.tpl__)
`platzky.create_app_from_config(config)` - creates _platzky_ application.
`platzky.sendmail(receiver_email, subject, message)`- sends email from configured account
