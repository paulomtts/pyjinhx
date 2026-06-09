from __future__ import annotations

import os
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound

from .finder import Finder
from ..utils import tag_name_to_template_filenames

if TYPE_CHECKING:
    from .base import BaseComponent
    from .renderer import Renderer


def get_loader_root(environment: Environment) -> str:
    loader = environment.loader
    if not isinstance(loader, FileSystemLoader):
        raise ValueError("Jinja2 loader must be a FileSystemLoader")
    return Finder.get_loader_root(loader)


def get_finder_for_root(renderer: Renderer, search_root: str) -> Finder:
    finder = renderer._template_finder_cache.get(search_root)
    if finder is None:
        finder = Finder(search_root)
        renderer._template_finder_cache[search_root] = finder
    return finder


def load_template_for_component(
    renderer: Renderer,
    component: BaseComponent,
    *,
    template_source: str | None,
    template_path: str | None,
) -> Template:
    environment = renderer.environment
    if template_source is not None:
        return environment.from_string(template_source)

    if template_path is not None:
        loader_root = get_loader_root(environment)
        relative_path = os.path.relpath(template_path, loader_root)
        return environment.get_template(relative_path)

    if type(component).__name__ == "BaseComponent":
        raise FileNotFoundError(
            "No template found. Use a BaseComponent subclass with an adjacent template file, "
            "or use Renderer.render() with PascalCase tags."
        )

    loader_root = get_loader_root(environment)
    relative_template_paths = Finder.get_relative_template_paths(
        component_dir=Finder.get_class_directory(type(component)),
        search_root=loader_root,
        component_name=type(component).__name__,
    )

    for relative_template_path in relative_template_paths:
        try:
            return environment.get_template(relative_template_path)
        except TemplateNotFound:
            continue

    if type(component).__module__.startswith("pyjinhx.builtins"):
        component_dir = Finder.get_class_directory(type(component))
        for filename in tag_name_to_template_filenames(type(component).__name__):
            candidate_path = os.path.join(component_dir, filename)
            if os.path.isfile(candidate_path):
                with open(candidate_path, encoding="utf-8") as template_file:
                    return environment.from_string(template_file.read())

    raise TemplateNotFound(
        ", ".join(relative_template_paths) if relative_template_paths else "unknown"
    )


def find_template_for_tag(renderer: Renderer, tag_name: str) -> str:
    loader_root = get_loader_root(renderer.environment)
    finder = get_finder_for_root(renderer, loader_root)
    return finder.find_template_for_tag(tag_name)
