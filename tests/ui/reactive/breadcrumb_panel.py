from typing import Annotated, Any

from pyjinhx import PjxKey, ReactiveComponent

from pyjinhx.builtins import PJXBreadcrumb

from tests.reactive_test_support import Keys


class BreadcrumbPanel(ReactiveComponent, react={Keys.TODOS}):
    """Reactive component whose nested builtin (PJXBreadcrumb) supplies a CSS asset
    that may not yet be on the page — mirrors nori's reactive TableWorkbench, the
    #184 reopen case."""

    panel_id: Annotated[str, PjxKey()]
    breadcrumb: Any = None

    @classmethod
    def load(cls, panel_id: str) -> "BreadcrumbPanel":
        return cls(
            id=f"breadcrumb-panel-{panel_id}",
            panel_id=panel_id,
            breadcrumb=PJXBreadcrumb(items=[("Library", None), ("Finance", None)]),
        )
