from pyjinhx.builtins import (
    PJXChipInput,
    PJXFormField,
    PJXPasswordInput,
    PJXSegmentedControl,
    PJXToggleSwitch,
)


def chip_input():
    return PJXChipInput(
        name="tags",
        values=["python", "jinja2", "htmx"],
        placeholder="Add tag…",
    ).render()


def form_field():
    return PJXFormField(
        label="Email address",
        for_id="demo-email",
        content='<input id="demo-email" type="email" name="email" placeholder="you@example.com">',
        help="We'll never share your email with anyone.",
        required=True,
    ).render()


def toggle_switch():
    return PJXToggleSwitch(name="notifications", checked=True, label="Email notifications").render()


def segmented_control():
    return PJXSegmentedControl(
        name="view",
        options=[("list", "List"), ("grid", "Grid"), ("table", "Table")],
        selected="grid",
    ).render()


def password_input():
    return PJXPasswordInput(
        name="password",
        placeholder="Enter your password",
        autocomplete="current-password",
        required=True,
    ).render()


DEMOS = {
    "PJXChipInput": (chip_input, 160),
    "PJXFormField": (form_field, 200),
    "PJXToggleSwitch": (toggle_switch, 120),
    "PJXSegmentedControl": (segmented_control, 120),
    "PJXPasswordInput": (password_input, 140),
}
