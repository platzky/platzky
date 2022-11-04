# APP_NAME is name of whole application, it will be shown e.g. in browser as title
APP_NAME: platzky

# DB is mapping with database configuration. It varies depending on TYPE.
# TYPE of database. Allowed are: json_file, google_json, grqph_ql
# Depending on TYPE there are different setups:
# - json_file has PATH - path where database json is stored
# - google_json has:
#   - BUCKET_NAME - name of bucket in google cloud
#   - SOURCE_BLOB_NAME - name of source blob in google cloud
# - graph_ql has:
#   - CMS_ENDPOINT
#   - CMS_TOKEN
DB:
  TYPE: json_file
  PATH: "../tests/e2e_tests/db.json"

# SECRET_KEY - flask's secret key
SECRET_KEY: testing-key

BABEL_TRANSLATION_DIRECTORIES: locale
BABEL_DEFAULT_LOCALE: en
SITEMAP_INCLUDE_RULES_WITHOUT_PARAMS: 'True'
SESSION_COOKIE_DOMAIN: www.platzky.localhost:5000
-
# DOMAINS - list of domains within which application should be operable
DOMAINS:
- www.platzky.localhost:5000
- www.platzkypl.localhost:5000

# MAIN_DOMAIN - main domain of application
MAIN_DOMAIN: www.platzky.localhost:5000

# DOMAIN_TO_LANG - mapping domain to language if page supports multilanguage and multidomain case
DOMAIN_TO_LANG:
  www.platzky.localhost:5000: en
  www.platzkypl.localhost:5000: pl

# LANGUAGES - list of languages supported by application with mapping:
# en - name of language
#   name - name which will be displayed
#   flag - name of flag which should be displayed instead of lang name
#   domain - default domain of language

LANGUAGES:
  en:
    name: English
    flag: uk
    domain: www.platzky.localhost:5000
  pl:
    name: polski
    flag: pl
    domain: www.platzkypl.localhost:5000
