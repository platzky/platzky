"""Sphinx configuration for Platzky documentation."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Project information
project = "Platzky"
copyright = "2025, Platzky Contributors"
author = "Platzky Contributors"

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML output options
html_theme = "alabaster"
html_static_path = ["_static"]

html_theme_options = {
    "description": "Not only blog engine",
    "github_user": "platzky",
    "github_repo": "platzky",
    "github_banner": True,
    "github_type": "star",
    "fixed_sidebar": True,
}

html_sidebars = {
    "**": [
        "about.html",
        "navigation.html",
        "relations.html",
        "searchbox.html",
    ]
}

# Autodoc settings
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "flask": ("https://flask.palletsprojects.com/en/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
