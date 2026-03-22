from fastapi.testclient import TestClient

from tests.builtins_gallery.app import create_app


def test_builtins_gallery_page_renders_all_components():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    for class_fragment in (
        "px-badge",
        "px-modal",
        "px-notification",
        "px-popover-trigger",
        "px-loading-overlay",
        "px-tooltip",
        "px-alert",
        "px-dropdown",
        "px-drawer",
        "px-progress",
        "px-skeleton",
        "px-empty-state",
        "px-divider",
        "px-spinner",
        "px-avatar",
        "px-card",
        "px-breadcrumb",
        "px-tab-group",
        "px-region",
        "px-region-trigger",
    ):
        assert class_fragment in text, f"missing {class_fragment}"


def test_builtins_gallery_static_design_system_css():
    client = TestClient(create_app())
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "--surface:" in response.text
