import yaml

def is_db_ok(mapping):
    if 'DB' not in mapping:
        raise Exception("DB not set")
    if 'type' not in mapping['DB']:
        raise Exception("DB type is not set")
    if mapping['DB']['type'] not in ['graphQl', 'json_file']:
        raise Exception("DB type is not supported")
    return True

class Config():
    def __init__(self, mapping):
        if is_db_ok(mapping):
            self.config = mapping
        else:
            raise Exception("Config is wrong")

    def add_translations_dir(self, absolute_translation_dir):
        self.config["BABEL_TRANSLATION_DIRECTORIES"] += ";" + absolute_translation_dir

    def asdict(self):
        return self.config


def get_config_mapping(base_config):
    default_config = {
        "USE_WWW": True,
        "SEO_PREFIX": "/",
        "BLOG_PREFIX": "/",
        "LANG_MAP": {},
        "DOMAIN_TO_LANG": {}
    }

    config = default_config | base_config
    babel_format_dir = ";".join(config.get("TRANSLATION_DIRECTORIES", []))
    config["BABEL_TRANSLATION_DIRECTORIES"] = babel_format_dir
    return config


def from_file(absolute_config_path):
    with open(absolute_config_path, "r") as stream:
        file_config = yaml.safe_load(stream)
    file_config["CONFIG_PATH"] = absolute_config_path
    return from_mapping(file_config)


def from_mapping(mapping):
    config_dict = get_config_mapping(mapping)
    return Config(config_dict)
