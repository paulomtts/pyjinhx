# Parser & Tag

Public API for parsing HTML strings that contain PascalCase component tags.

See [PascalCase Tags](../guide/tags.md) for usage patterns and [Renderer](renderer.md) for the high-level render API.

## Parser

```python
class Parser(HTMLParser):
    root_nodes: list[Tag | str]
```

HTML parser that identifies PascalCase component tags and builds a tree of `Tag` nodes. Standard HTML tags are passed through as raw strings.

### Usage

```python
from pyjinhx.tags import Parser, Tag

parser = Parser()
parser.feed('<Button text="OK"/><p>plain html</p>')
for node in parser.root_nodes:
    if isinstance(node, Tag):
        print(node.name, node.attrs)
    else:
        print("raw:", node)
```

`Renderer.render()` uses `Parser` internally. Use `Parser` directly when you need the parse tree without rendering (custom tooling, linting, AST transforms).

### PascalCase detection

Tags matching `^[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*)?$` are treated as components (e.g. `Button`, `ActionButton`). All other tags pass through unchanged.

## Tag

```python
@dataclass
class Tag:
    name: str
    attrs: dict[str, str]
    children: list[Tag | str]
```

Represents a parsed PascalCase component tag.

| Field | Description |
|-------|-------------|
| `name` | Tag name (e.g. `"Button"`, `"UserCard"`) |
| `attrs` | Attribute name → value mapping from the tag |
| `children` | Nested `Tag` nodes or raw text/HTML strings |

Inner text between opening and closing tags becomes string children. Self-closing tags have an empty `children` list.

```python
# <Card title="Note">Hello</Card>
# Tag(name="Card", attrs={"title": "Note"}, children=["Hello"])
```
