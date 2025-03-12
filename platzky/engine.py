import os

from flask import Flask, request, session
from flask_babel import Babel

from platzky.config import Config


class Engine(Flask):
    def __init__(self, config: Config, db, import_name):
        super().__init__(import_name)
        self.config.from_mapping(config.model_dump(by_alias=True))
        self.db = db
        self.notifiers = []
        self.login_methods = []
        self.dynamic_body = ""
        self.dynamic_head = ""
        directory = os.path.dirname(os.path.realpath(__file__))
        locale_dir = os.path.join(directory, "locale")
        config.translation_directories.append(locale_dir)

        babel_translation_directories = ";".join(config.translation_directories)
        self.babel = Babel(
            self,
            locale_selector=self.get_locale,
            default_translation_directories=babel_translation_directories,
        )

    def notify(self, message: str):
        for notifier in self.notifiers:
            notifier(message)

    def add_notifier(self, notifier):
        self.notifiers.append(notifier)

    def add_login_method(self, login_method):
        self.login_methods.append(login_method)

    def add_dynamic_body(self, body: str):
        self.dynamic_body += body

    def add_dynamic_head(self, body: str):
        self.dynamic_head += body

    def get_locale(self) -> str:
-        domain = request.headers["Host"]
+        domain = request.headers.get("Host", "localhost")
        domain_to_lang = self.config.get("DOMAIN_TO_LANG")

        languages = self.config.get("LANGUAGES", {}).keys()
        backup_lang = session.get(
            "language",
            request.accept_languages.best_match(languages, "en"),
        )

        if domain_to_lang:
            lang = domain_to_lang.get(domain, backup_lang)
        else:
            lang = backup_lang

        session["language"] = lang
        return lang
