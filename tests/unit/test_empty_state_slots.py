from pyjinhx.builtins import PJXBadge, PJXEmptyState


def test_empty_state_default_render_has_no_image_or_actions():
    html = str(
        PJXEmptyState(
            id="es-plain",
            title="No results",
            description="Adjust filters or create a new item.",
        ).render()
    )
    assert 'class="pjx-empty-state"' in html
    assert 'class="pjx-empty-state__image"' not in html
    assert 'class="pjx-empty-state__actions"' not in html


def test_empty_state_image_renders_above_title():
    html = str(
        PJXEmptyState(
            id="es-image",
            title="No results",
            image='<img src="/mascot.svg" alt="">',
        ).render()
    )
    assert '<div class="pjx-empty-state__image"><img src="/mascot.svg" alt=""></div>' in html
    assert html.index('class="pjx-empty-state__image"') < html.index('class="pjx-empty-state__title"')


def test_empty_state_actions_renders_all_items():
    html = str(
        PJXEmptyState(
            id="es-actions",
            title="No results",
            actions=[
                PJXBadge(id="es-badge-1", label="Try a template"),
                PJXBadge(id="es-badge-2", label="Import data"),
            ],
        ).render()
    )
    assert '<div class="pjx-empty-state__actions">' in html
    assert "Try a template" in html
    assert "Import data" in html


def test_empty_state_action_renders_before_actions():
    html = str(
        PJXEmptyState(
            id="es-both",
            title="No results",
            action="<button>Create item</button>",
            actions=["<button>Use a template</button>", "<button>Import</button>"],
        ).render()
    )
    assert '<div class="pjx-empty-state__action"><button>Create item</button></div>' in html
    assert "<button>Use a template</button>" in html
    assert "<button>Import</button>" in html
    assert html.index('class="pjx-empty-state__action"') < html.index('class="pjx-empty-state__actions"')
