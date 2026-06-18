from pyjinhx.builtins import (
    PJXAvatar,
    PJXAvatarStack,
    PJXBadge,
    PJXBreadcrumb,
    PJXButton,
    PJXCard,
    PJXDivider,
    PJXEmptyState,
    PJXIcon,
    PJXProgress,
    PJXSkeleton,
    PJXSpinner,
)


def badge():
    return PJXBadge(label="Active", color="brand").render()


def card():
    return PJXCard(title="Quarterly report", body="Revenue grew 12% over Q1.", footer="Updated today").render()


def divider():
    return PJXDivider(orientation="horizontal", label="or continue with").render()


def spinner():
    return PJXSpinner(size="md", label="Loading data").render()


def avatar():
    return PJXAvatar(initials="JD", size="md", alt="Jane Doe").render()


def avatar_stack():
    return PJXAvatarStack(
        avatars=[
            PJXAvatar(initials="AB", size="sm", alt="Alice Brown"),
            PJXAvatar(initials="CD", size="sm", alt="Carol Davis"),
            PJXAvatar(initials="EF", size="sm", alt="Eve Foster"),
        ],
        extra_count=4,
    ).render()


def breadcrumb():
    return PJXBreadcrumb(items=[("Home", "/"), ("Projects", "/projects"), ("Dashboard", None)]).render()


def skeleton():
    return PJXSkeleton(variant="text", lines=3).render()


def progress():
    return PJXProgress(value=65, max=100, label="Upload progress").render()


def empty_state():
    return PJXEmptyState(
        title="No results",
        description="Try a different search term.",
        actions=['<button class="pjx-demo-btn">Clear filters</button>'],
    ).render()


def icon():
    return PJXIcon(name="plus", size=24, label="Add item").render()


def button():
    return PJXButton(center="Save", variant="primary").render()


DEMOS = {
    "PJXBadge": (badge, 120),
    "PJXCard": (card, 220),
    "PJXDivider": (divider, 120),
    "PJXSpinner": (spinner, 120),
    "PJXAvatar": (avatar, 120),
    "PJXAvatarStack": (avatar_stack, 120),
    "PJXBreadcrumb": (breadcrumb, 120),
    "PJXSkeleton": (skeleton, 160),
    "PJXProgress": (progress, 120),
    "PJXEmptyState": (empty_state, 260),
    "PJXIcon": (icon, 120),
    "PJXButton": (button, 120),
}
