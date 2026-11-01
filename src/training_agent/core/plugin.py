"""Plugin base class and loader."""

from __future__ import annotations

import importlib
import inspect
from abc import ABC
from pathlib import Path

import yaml


class Plugin(ABC):
    """Base class of every plugin.

    `name` must match the plugin's key in config/features.yaml. Each plugin
    file defines exactly one concrete Plugin subclass. Adding a feature means
    adding such a file plus one entry in features.yaml, nothing else.
    """

    name: str


def load_enabled_plugins(config_path: str | Path, section: str) -> list[Plugin]:
    """Instantiate every enabled plugin of one features.yaml section.

    For each entry with `enabled: true`, import its `module` and instantiate
    the single concrete Plugin subclass defined in that module.
    """
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    plugins: list[Plugin] = []
    for name, spec in (config.get(section) or {}).items():
        if not spec.get("enabled"):
            continue
        module = importlib.import_module(spec["module"])
        classes = [
            c
            for c in vars(module).values()
            if inspect.isclass(c)
            and issubclass(c, Plugin)
            and c.__module__ == module.__name__
            and not inspect.isabstract(c)
        ]
        if len(classes) != 1:
            raise RuntimeError(f"{spec['module']} must define exactly one Plugin, found {len(classes)}")
        plugins.append(classes[0]())
    return plugins
