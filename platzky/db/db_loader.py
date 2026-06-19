"""Dynamic database module loader based on configuration type."""

import importlib
import types

from platzky.db.db import DB, DBConfig


def get_db(db_config: DBConfig) -> DB:
    """Load and initialise the database backend specified in *db_config*."""
    db_name = db_config.type
    db = get_db_module(db_name)
    return db.db_from_config(db_config)


def get_db_module(db_type: str) -> types.ModuleType:
    """
    Import the db module for db_type from the platzky.db package.
    :param db_type: name of db module
    :return: db module
    """
    parent_module_name = ".".join(__name__.split(".")[:-1])
    return importlib.import_module(f"{parent_module_name}.{db_type}_db")
