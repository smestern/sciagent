"""Minimal setup.py to map top-level templates/ into the sciagent package.

All project metadata lives in pyproject.toml.  This file exists solely
because pyproject.toml's [tool.setuptools.packages.find] cannot map a
top-level directory into a sub-package.  setuptools.build_meta picks it
up automatically — no pre-install hook is needed.
"""

from setuptools import setup, find_packages

setup(
    packages=find_packages("src") + ["sciagent.templates"],
    package_dir={
        "": "src",
        "sciagent.templates": "templates",
    },
    package_data={
        "sciagent.prompts": ["*.md"],
        "sciagent.web": [
            "static/css/*.css",
            "static/js/*.js",
            "templates/*.html",
        ],
        "sciagent.templates": [
            "*.md",
            "*.yaml",
            "*.yml",
            "**/*.md",
            "**/*.yaml",
            "**/*.yml",
        ],
    },
)
