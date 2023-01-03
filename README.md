# platzky

Blog engine in python 

## Configuration

For details check `config.yml.tpl` file.


# API
`platzky.config.from_file(path_to_config)` - creates _platzky_ config from file (see __config.yml.tpl__)
`platzky.create_app_from_config(config)` - creates _platzky_ application.
`platzky.sendmail(receiver_email, subject, message)`- sends email from configured account
