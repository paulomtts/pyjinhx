"""Tests for the discovery class registry and its built-then-swap publish."""

import logging
import threading
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.discovery import build_registry, get_class, walk_templates

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


class AlphaCard(BaseComponent):
    pass


class NestedWidget(BaseComponent):
    pass


class Unrelated(BaseComponent):
    pass


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def test_registry_is_empty_before_any_build():
    assert get_class("alpha_card") is None


def test_get_class_returns_none_for_unknown_tag_never_raises():
    assert get_class("no_such_tag_anywhere") is None
    assert get_class("") is None


def test_registry_state_is_not_a_bare_module_level_container():
    """The purity scan in test_discovery.py flags dict/list/set module globals.
    Registry state must be owned by a holder object so the walk stays visibly
    stateless."""
    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []


def test_build_registers_classes_whose_tag_is_on_disk():
    build_registry(DISCOVERY_DIR, [AlphaCard, NestedWidget])
    assert get_class("alpha_card") is AlphaCard
    assert get_class("nested_widget") is NestedWidget


def test_build_skips_classes_with_no_template_on_disk():
    build_registry(DISCOVERY_DIR, [AlphaCard, Unrelated])
    assert get_class("unrelated") is None


def test_build_skips_templates_with_no_matching_class():
    build_registry(DISCOVERY_DIR, [AlphaCard])
    assert get_class("deep_widget") is None
    assert get_class("beta") is None


def test_build_accepts_str_template_dir():
    build_registry(str(DISCOVERY_DIR), [AlphaCard])
    assert get_class("alpha_card") is AlphaCard


def test_rebuild_replaces_the_previous_mapping_entirely():
    build_registry(DISCOVERY_DIR, [AlphaCard, NestedWidget])
    build_registry(DISCOVERY_DIR, [NestedWidget])
    assert get_class("nested_widget") is NestedWidget
    assert get_class("alpha_card") is None


def test_failed_walk_leaves_the_published_registry_untouched(tmp_path):
    build_registry(DISCOVERY_DIR, [AlphaCard])
    with pytest.raises(NotADirectoryError):
        build_registry(tmp_path / "nope", [NestedWidget])
    assert get_class("alpha_card") is AlphaCard
    assert get_class("nested_widget") is None


def test_publish_is_a_single_rebind_not_incremental_mutation():
    """A reader that grabbed the live mapping before a rebuild keeps seeing the
    complete old mapping — the build never writes into the published dict."""
    build_registry(DISCOVERY_DIR, [AlphaCard])
    before = discovery._registry.mapping
    build_registry(DISCOVERY_DIR, [NestedWidget])
    assert before == {"alpha_card": AlphaCard}
    assert discovery._registry.mapping is not before


def test_concurrent_builds_never_expose_a_partial_mapping():
    complete = ({"alpha_card": AlphaCard}, {"nested_widget": NestedWidget})
    observed: list[dict[str, type]] = []
    stop = threading.Event()

    def read():
        while not stop.is_set():
            observed.append(discovery._registry.mapping)

    def build(classes):
        for _ in range(20):
            build_registry(DISCOVERY_DIR, classes)

    reader = threading.Thread(target=read)
    reader.start()
    builders = [
        threading.Thread(target=build, args=([AlphaCard],)),
        threading.Thread(target=build, args=([NestedWidget],)),
    ]
    for thread in builders:
        thread.start()
    for thread in builders:
        thread.join()
    stop.set()
    reader.join()

    assert observed
    assert all(mapping in ({},) + complete for mapping in observed)


class PkgA:
    class AlphaCard(BaseComponent):
        pass


class PkgB:
    class AlphaCard(BaseComponent):
        pass


class PkgC:
    class AlphaCard(BaseComponent):
        pass


def warnings_in(caplog):
    """The WARNING records captured so far."""
    return [record for record in caplog.records if record.levelno == logging.WARNING]


def test_colliding_tags_warn_naming_the_tag(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
    assert len(warnings_in(caplog)) == 1
    assert "alpha_card" in warnings_in(caplog)[0].getMessage()


def test_collision_warning_names_the_colliding_classes(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
    message = warnings_in(caplog)[0].getMessage()
    assert f"{__name__}.PkgA.AlphaCard" in message
    assert f"{__name__}.PkgB.AlphaCard" in message


def test_collision_warning_uses_lazy_percent_formatting(caplog):
    """The record still carries its args, so the message was never pre-formatted."""
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
    record = warnings_in(caplog)[0]
    assert record.args
    assert "%s" in record.msg


def test_collision_warns_once_even_though_the_stem_is_on_disk_twice(caplog):
    """`alpha_card.pjx` exists at the root and under `forms/`; the walk yields
    both, but the collision is one problem and gets one warning."""
    found = [c for c in walk_templates(DISCOVERY_DIR) if c.tag_name == "alpha_card"]
    assert len(found) == 2
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
    assert len(warnings_in(caplog)) == 1


def test_collision_winner_is_last_by_qualified_name(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
    assert get_class("alpha_card") is PkgB.AlphaCard


def test_collision_winner_does_not_depend_on_input_order(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard])
        forward = get_class("alpha_card")
        build_registry(DISCOVERY_DIR, [PkgB.AlphaCard, PkgA.AlphaCard])
        backward = get_class("alpha_card")
    assert forward is backward
    assert forward is PkgB.AlphaCard


def test_three_way_collision_has_one_winner_and_one_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgC.AlphaCard, PkgA.AlphaCard, PkgB.AlphaCard])
    assert get_class("alpha_card") is PkgC.AlphaCard
    assert len(warnings_in(caplog)) == 1


def test_three_way_collision_winner_survives_reordering(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [PkgA.AlphaCard, PkgB.AlphaCard, PkgC.AlphaCard])
        forward = get_class("alpha_card")
        build_registry(DISCOVERY_DIR, [PkgC.AlphaCard, PkgB.AlphaCard, PkgA.AlphaCard])
        backward = get_class("alpha_card")
    assert forward is backward
    assert forward is PkgC.AlphaCard


def test_distinct_tags_never_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [AlphaCard, NestedWidget, Unrelated])
    assert warnings_in(caplog) == []
    assert get_class("alpha_card") is AlphaCard
    assert get_class("nested_widget") is NestedWidget


def test_orphan_template_never_warns(caplog):
    """`beta.pjx` sits on disk with no class claiming it — normal, not a collision."""
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [AlphaCard])
    assert warnings_in(caplog) == []
    assert get_class("beta") is None
