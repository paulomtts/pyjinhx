from pyjinhx.builtins import (
    Avatar,
    AvatarStack,
    Badge,
    Breadcrumb,
    Card,
    Divider,
    EmptyState,
    Progress,
    Skeleton,
    Spinner,
)


def badge():
    return Badge(label="Active", color="brand")


def card():
    return Card(title="Quarterly report", body="Revenue grew 12% over Q1.", footer="Updated today")


def divider():
    return Divider(orientation="horizontal", label="or continue with")


def spinner():
    return Spinner(size="md", label="Loading data")


def avatar():
    return Avatar(initials="JD", size="md", alt="Jane Doe")


def avatar_stack():
    return AvatarStack(
        avatars=[
            Avatar(initials="AB", size="sm", alt="Alice Brown"),
            Avatar(initials="CD", size="sm", alt="Carol Davis"),
            Avatar(initials="EF", size="sm", alt="Eve Foster"),
        ],
        extra_count=4,
    )


def breadcrumb():
    return Breadcrumb(items=[("Home", "/"), ("Projects", "/projects"), ("Dashboard", None)])


def skeleton():
    return Skeleton(variant="text", lines=3)


def progress():
    return Progress(value=65, max=100, label="Upload progress")


def empty_state():
    return EmptyState(
        title="No results",
        description="Try a different search term.",
        actions=['<button class="px-demo-btn">Clear filters</button>'],
    )


DEMOS = {
    "Badge": (badge, 120),
    "Card": (card, 220),
    "Divider": (divider, 120),
    "Spinner": (spinner, 120),
    "Avatar": (avatar, 120),
    "AvatarStack": (avatar_stack, 120),
    "Breadcrumb": (breadcrumb, 120),
    "Skeleton": (skeleton, 160),
    "Progress": (progress, 120),
    "EmptyState": (empty_state, 260),
}
