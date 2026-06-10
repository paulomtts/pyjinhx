from pyjinhx.builtins import Badge, Card


def badge():
    return Badge(label="Active", color="brand")


def card():
    return Card(title="Quarterly report", body="Revenue grew 12% over Q1.", footer="Updated today")


DEMOS = {
    "Badge": (badge, 120),
    "Card": (card, 220),
}
