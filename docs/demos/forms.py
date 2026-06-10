from pyjinhx.builtins import (
    ChipInput,
    FormField,
    PasswordInput,
    SegmentedControl,
    ToggleSwitch,
)


def chip_input():
    return ChipInput(
        name="tags",
        values=["python", "jinja2", "htmx"],
        placeholder="Add tag…",
    )


def form_field():
    return FormField(
        label="Email address",
        for_id="demo-email",
        content='<input id="demo-email" type="email" name="email" placeholder="you@example.com">',
        help="We'll never share your email with anyone.",
        required=True,
    )


def toggle_switch():
    return ToggleSwitch(name="notifications", checked=True, label="Email notifications")


def segmented_control():
    return SegmentedControl(
        name="view",
        options=[("list", "List"), ("grid", "Grid"), ("table", "Table")],
        selected="grid",
    )


def password_input():
    return PasswordInput(
        name="password",
        placeholder="Enter your password",
        autocomplete="current-password",
        required=True,
    )


DEMOS = {
    "ChipInput": (chip_input, 160),
    "FormField": (form_field, 200),
    "ToggleSwitch": (toggle_switch, 120),
    "SegmentedControl": (segmented_control, 120),
    "PasswordInput": (password_input, 140),
}
