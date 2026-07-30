"""L0.4.4/L0.4.6 render — single-level pipeline and public API.

Descriptor read → context build → Jinja render → single parse → RenderedLevel
(render_level, internal). serialize(render_level(...)) closes the loop into a
finished HTML string for a childless component (render, public API).
"""

import html
from typing import cast

import jinja2

from pyjinhx2.component import BaseComponent, PjxSlot, _pascal_to_snake
from pyjinhx2.discovery import get_class
from pyjinhx2.segments import ChildRef, RenderedLevel, VerbatimParser, serialize
from pyjinhx2.session import RenderSession


def _passthrough_markup(ref: ChildRef) -> str:
    """Markup for a ChildRef whose tag no component class claims.

    An unregistered PascalCase tag is ordinary markup — a web component, or a
    tag someone meant to ship as-is — so it goes back into the stream instead of
    raising (architecture-overview: a registry miss is an answer, not an error).

    Reconstructed from the ChildRef's own fields, not echoed: the parse that
    produced it kept the tag, the attrs and the inner text, and dropped the raw
    source, so the original quoting style and spacing are not recoverable here.
    ``inner`` was captured verbatim and is emitted raw; attr values are
    re-escaped because they arrive from the parse already unescaped.
    """
    attrs = "".join(
        f' {name}="{html.escape(value, quote=True)}"'
        for name, value in ref.attrs.items()
    )
    if ref.inner is None:
        return f"<{ref.tag}{attrs}/>"
    return f"<{ref.tag}{attrs}>{ref.inner}</{ref.tag}>"


def _children_field(cls: type[BaseComponent]) -> str | None:
    """The declared field a paired tag's body text is assigned to, if any.

    Which fields are slots is a type-level fact frozen in the descriptor; which
    single one receives nested children is decided here, at expansion time, so
    a class can carry several raw-HTML slots and still name one target.
    """
    fields = getattr(cls, "model_fields", {})
    marked = [
        name
        for name, field in fields.items()
        if any(isinstance(m, PjxSlot) and m.children for m in field.metadata)
    ]
    if len(marked) > 1:
        raise ValueError(
            f"{cls.__name__} marks {len(marked)} fields as the children target "
            f"({', '.join(sorted(marked))}); exactly one field may use Children."
        )
    if marked:
        return marked[0]
    named = getattr(cls, "_pjx_children_field", None)
    if isinstance(named, str) and named in fields:
        return named
    return None


def _instantiate_child(ref: ChildRef, cls: type[BaseComponent]) -> BaseComponent:
    """Construct ``cls`` from a resolved ChildRef's attrs and body text.

    Construction is the whole coercion step: the class's own validators turn
    JSON-looking attr strings into lists/dicts/models and fill an omitted id, so
    nothing here re-implements them and their errors reach the caller unchanged.

    A paired tag's ``inner`` is merged raw, not parsed: it becomes a field value
    that the child's own template re-emits, so the tags inside it are cut out by
    the child's own parse and this level still parses exactly once.
    """
    kwargs: dict[str, str] = dict(ref.attrs)
    if ref.inner is not None and ref.inner.strip():
        field = _children_field(cls)
        if field is None:
            raise ValueError(
                f"<{ref.tag}> was given body text, but {cls.__name__} names no "
                f"children field; mark one field Children or write the tag "
                f"self-closing."
            )
        if field in kwargs:
            raise ValueError(
                f"<{ref.tag}> received both body text and a {field!r} attribute; "
                f"supply one."
            )
        kwargs[field] = ref.inner
    return cls(**kwargs)


def _fill_children(level: RenderedLevel) -> list[tuple[int, BaseComponent]]:
    """Resolve each ChildRef in ``level`` against the class registry, in place.

    Tags no class claims stop being holes here and go back to being markup.
    Tags that do resolve are instantiated once, in document order, and returned
    with their segment index so the recursive step can render each one and
    splice it back where its ChildRef still sits.
    """
    pending: list[tuple[int, BaseComponent]] = []
    for index, segment in enumerate(level.segments):
        if not isinstance(segment, ChildRef):
            continue
        cls = get_class(_pascal_to_snake(segment.tag))
        if cls is None:
            level.segments[index] = _passthrough_markup(segment)
            continue
        pending.append(
            (index, _instantiate_child(segment, cast(type[BaseComponent], cls)))
        )
    return pending


def render_level(
    component: BaseComponent,
    session: "RenderSession",
    chain: tuple[str, ...] = (),
) -> RenderedLevel:
    """Render one component level: template → one parse → RenderedLevel.

    Args:
        component: A valid BaseComponent instance (construction-time validation passed).
        session: RenderSession providing Jinja environment and hooks.
        chain: Class names of the components already being rendered on this
            call path, outermost first. Passed by value down the recursion so
            each branch sees its own ancestors and nothing else.

    Returns:
        RenderedLevel with segments (str | ChildRef), root_span, descriptor.

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        ValueError: If a component re-enters its own render chain (cycle).
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
    """
    # Phase 1: Descriptor read
    descriptor = component.__class__.__pjx_descriptor__

    # Phase 2: Context build
    context = {}
    for field_name in component.__class__.model_fields:
        field_value = getattr(component, field_name)
        context[field_name] = field_value

    # Phase 3: Jinja render with autoescape ON
    jinja_env = session.jinja_env
    prefix = f"{component.__class__.__name__} (template: {descriptor.template_path}): "

    # A component whose subtree instantiates itself or an ancestor would recurse
    # forever; the chain is the current call path only, so the same class on two
    # sibling branches is fine (ADR 0004: nesting/load chains are the only cycle
    # vector left in v2).
    name = component.__class__.__name__
    if name in chain:
        cycle = chain[chain.index(name) :]
        raise ValueError(f"{prefix}cycle detected: {' -> '.join((*cycle, name))}")
    chain = (*chain, name)

    try:
        template = jinja_env.get_template(str(descriptor.template_path))
    except jinja2.TemplateNotFound as err:
        raise jinja2.TemplateNotFound(
            err.name, message=f"{prefix}template file not found"
        ) from err
    output_string = template.render(context)

    # Phase 4: Single parse via VerbatimParser
    parser = VerbatimParser()
    parser.feed(output_string)
    parser.close()

    # Validate single-root rule
    try:
        parser.enforce_single_root()
    except ValueError as err:
        raise ValueError(f"{prefix}{err}") from err

    # Return RenderedLevel
    level = RenderedLevel(
        segments=cast(list[str | ChildRef | RenderedLevel], parser.segments),
        root_span=parser.root_span or (0, 0),
        descriptor=descriptor,
    )
    # Unregistered tags stop being holes here, one pass per level (ADR 0005);
    # the ones that do resolve become instances the recursive step consumes.
    for index, child in _fill_children(level):
        # Each child gets its own render_level call, so it does its own single
        # parse and enters this list as a whole object — never text spliced into
        # text, which is what keeps a child's markup un-reparsed and un-escaped.
        level.segments[index] = render_level(child, session, chain)
    return level


def render(component: BaseComponent, session: "RenderSession | None" = None) -> str:
    """Render a component to a final HTML string (public API).

    Thin wrapper closing the loop for a childless component: render_level()
    produces one component's RenderedLevel, serialize() joins its segments
    back into markup. Internal/recursive callers (L1) call render_level()
    directly instead, since they need the RenderedLevel, not a string.

    Args:
        component: A valid BaseComponent instance.
        session: RenderSession providing the Jinja environment. Defaults to
            a fresh RenderSession() when omitted, so callers outside the
            kernel don't need to construct one by hand.

    Returns:
        The component's rendered markup as a finished HTML string.

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
        AssertionError: If a segment reaching serialize() is neither str
            nor RenderedLevel (unresolved ChildRef reaching the boundary).
    """
    if session is None:
        session = RenderSession()
    level = render_level(component, session)
    return serialize(level)
