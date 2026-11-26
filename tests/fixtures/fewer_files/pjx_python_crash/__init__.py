"""A document whose Python block fails on import, kept out of shape P's package
so that publishing that package does not trip over it."""

import pyjinhx  # noqa: F401
