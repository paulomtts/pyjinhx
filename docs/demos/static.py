from pyjinhx.builtins import (
    PJXAccordion,
    PJXAccordionGroup,
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


def accordion():
    return PJXAccordion(label="What is pyjinhx?", content="<p>A Python/Jinja HTML component framework.</p>").render()


def accordion_group():
    return PJXAccordionGroup(
        mode="exclusive",
        gap="0.25rem",
        content=(
            PJXAccordion(label="Section A", content="<p>Content A.</p>").render()
            + PJXAccordion(label="Section B", open=False, content="<p>Content B.</p>").render()
            + PJXAccordion(label="Section C", open=False, content="<p>Content C.</p>").render()
        ),
    ).render()


def badge():
    return [
        PJXBadge(label="Active", color="brand").render(),
        PJXBadge(label="Error", color="error").render(),
        PJXBadge(label="Neutral", color="neutral").render(),
        PJXBadge(label="Beta", color="muted", shape="full").render(),
    ]


def card():
    return PJXCard(title="Quarterly report", body="Revenue grew 12% over Q1.", footer="Updated today").render()


def divider():
    return PJXDivider(orientation="horizontal", label="or continue with").render()


def spinner():
    return [
        PJXSpinner(size="sm", label="Loading data").render(),
        PJXSpinner(size="md", label="Loading data").render(),
        PJXSpinner(size="lg", label="Loading data").render(),
    ]


def avatar():
    return [
        PJXAvatar(initials="JD", size="sm", alt="Jane Doe").render(),
        PJXAvatar(initials="JD", size="md", alt="Jane Doe").render(),
        PJXAvatar(initials="JD", size="lg", alt="Jane Doe").render(),
    ]


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
    return [
        PJXSkeleton(variant="text", lines=3).render(),
        PJXSkeleton(variant="circle").render(),
        PJXSkeleton(variant="rect").render(),
    ]


def progress():
    return [
        PJXProgress(value=65, max=100, label="Upload progress").render(),
        PJXProgress(label="Processing").render(),
    ]


def empty_state():
    return PJXEmptyState(
        title="No results",
        description="Try a different search term.",
        actions=['<button class="pjx-demo-btn">Clear filters</button>'],
    ).render()


def icon():
    return [
        PJXIcon(name="plus", size=24, label="Add").render(),
        PJXIcon(name="search", size=24, label="Search").render(),
        PJXIcon(name="trash", size=24, label="Delete").render(),
        PJXIcon(name="settings", size=24, label="Settings").render(),
        PJXIcon(name="chevron-right", size=24, label="Next").render(),
    ]


def button():
    return [
        PJXButton(center="Save", variant="primary").render(),
        PJXButton(center="Cancel").render(),
        PJXButton(center="Saving", variant="primary", loading=True).render(),
        PJXButton(center="Disabled", disabled=True).render(),
    ]


DEMOS = {
    "PJXAccordion": (accordion, 160),
    "PJXAccordionGroup": (accordion_group, 260),
    "PJXBadge": (badge, 140),
    "PJXCard": (card, 220),
    "PJXDivider": (divider, 120),
    "PJXSpinner": (spinner, 140),
    "PJXAvatar": (avatar, 140),
    "PJXAvatarStack": (avatar_stack, 120),
    "PJXBreadcrumb": (breadcrumb, 120),
    "PJXSkeleton": (skeleton, 220),
    "PJXProgress": (progress, 170),
    "PJXEmptyState": (empty_state, 260),
    "PJXIcon": (icon, 140),
    "PJXButton": (button, 140),
}
