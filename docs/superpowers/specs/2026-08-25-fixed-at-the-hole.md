# Fixed at the hole — the five scenarios, before and after

Companion to [`2026-08-25-nested-freshness-design.md`](./2026-08-25-nested-freshness-design.md).
Each scenario as it behaves today and as it behaves once every child is resolved at
the moment its hole is filled.

Published as an artifact: <https://claude.ai/code/artifact/7849ea42-67b6-4a94-baf2-3f47dbd34133>

Panes are marked **measured** (a real run against v1.9.1, from the scratchpad
repros) or **designed** (a consequence of the spec, not an observation).

> **A cache entry never contains another component.**
>
> The render cache already obeys this — a hit restores the shell and leaves child
> holes as holes. The load cache does not. Every scenario below is a consequence of
> that one asymmetry.

## 1. Clean children still load — *unfiled*

Five reactive components nested in a chain, each declaring its own key. Nothing
dirtied, everything already on the client.

```python
class Level0(ReactiveComponent, react=("key0",)): ...   # <Level1/> in its template
class Level1(ReactiveComponent, react=("key1",)): ...   # <Level2/> in its template
```

**Today** *(measured)*

```text
cold render                loads: L0 L1 L2 L3 L4  (5)
L0 cached, rest evicted    loads:    L1 L2 L3 L4  (4)
no backend, request 2      loads: L0 L1 L2 L3 L4  (5)
```

A fully cached parent does not stop the descent — no cache holds a subtree, so the
renderer must go and get the children.

**After** *(designed)*

```text
nothing dirtied, client holds every region    loads: —   (0)

each hole emits:
<div id="level1" hx-preserve="true"></div>
```

The gate asks about dirtiness *before* loading. A clean subtree costs one
placeholder no matter how deep it goes.

## 2. Tag composition serves a stale key — *#1026*

The child's identity flows through the parent's data. The user moves from
conversation 1 to 2, dirtying `conversation`.

```python
class Shell(ReactiveComponent, react=("view",)):   # does NOT declare 'conversation'
    ...
```

```jinja
<div id="shell"><Child conversation="{{ conversation }}"/></div>
```

**Today** *(measured)*

```text
A  baseline           child.load: ['1']   stale: True
B  child cache=False  child.load: ['1']   stale: True
C  parent declares it child.load: ['2']   stale: False
```

The child's entry *is* evicted and its body *does* run — against a key read off a
parent that was not. Opting the child out of caching changes nothing.

**After** *(designed)*

```text
Shell (template: shell.pjx): child Child reacts to 'conversation', which this
request dirtied — but Shell was served from the load cache, so the props it
passed down are from an earlier request.

    react=("view", "conversation")
```

The parent depends on every key it passes down as an identity. The error says so,
and names the fix — which is scenario C, already working today.

## 3. Slot composition freezes the child — *#1026*

The parent builds its child in Python, so the child arrives already loaded. There is
no hole, and therefore no decision point.

**Today** *(measured)*

```python
content=Child.load(conversation=view)
```

```text
WITH a tier-2 backend
   shell.load() ran : False
   child.load() keys: NEVER
   serves stale     : True
```

The child's data sits inside the parent's cache entry. Nothing left to load — the
answer is already in the field.

**After** *(designed)*

```python
content=Child.ref(conversation=view)
```

```text
cached value holds:
   Ref(Child, {"conversation": "1"})
   ^ an instruction, not an answer

child.load() keys: ['2']
serves stale     : False
```

A reference cannot freeze. The parent's entry names the child; it doesn't contain
it.

## 4. A fresh parent names a different child — *condition 3*

The subtle one. `view` is dirtied but `conversation` is not — yet the reloaded
parent now points at a different conversation.

**A naive skip gate** *(designed)*

```text
Shell reloads    -> passes conversation="2"
Child's own keys -> clean
                 -> PRESERVE

client keeps markup for conversation="1"
```

A skip gate that only asked "were your keys dirtied?" would introduce a brand-new
staleness bug in the act of fixing the others.

**With the load-key match** *(designed)*

```text
manifest region load key : "1"
child now resolves to    : "2"
                         -> mismatch
                         -> condition 3 fails
                         -> the child loads
```

Condition 3 does two jobs: does the client have this region, and is it still the
same child.

## 5. A list where one row changed

Fifty rows, one dirtied. Each element is its own hole with its own decision.

```python
content=[Messages.ref(conversation=c) for c in ids]
```

```jinja
{% for c in content %}{{ c }}{% endfor %}
```

**Today** *(measured)*

```text
50 rows rendered
50 load() bodies run
49 results discarded by fan-out
```

Fan-out correctly ships only the one changed row. The other forty-nine were
fetched, formatted, rendered, and thrown away.

**After** *(designed)*

```text
1  loads and renders
49 emit <li id="row-7" hx-preserve="true">

REQUIRES a stable authored id per row:
   <li id="row-{{ conversation }}">
```

With auto `pjx-N` ids the gate fails and all fifty load — correct, no savings. This
is the one thing to get right for lists.

## What this does not fix

### Auto ids get no islands

`_auto_id()` is a process-unique counter (`_component.py:47`), so the same logical
region gets a new id on every render:

```text
same region, three consecutive requests:
  request 1: <section id="pjx-1">msgs-7</section>
  request 2: <section id="pjx-2">msgs-7</section>
  request 3: <section id="pjx-3">msgs-7</section>
```

htmx resolves a preserved element by the plain `id` via `getElementById`. A
placeholder saying `pjx-2` would find no live node called `pjx-2`, `hx-preserve`
would no-op, and the empty placeholder would ship — wiping the region. Conditions 3
and 4 both catch this, so the child simply loads instead. Correct, no savings, no
signal.

| No islands | Islands |
|---|---|
| `<section>{{ body }}</section>` | `<section id="messages-{{ conversation }}">{{ body }}</section>` |
| id minted per render → `pjx-1`, `pjx-2`, … | id stable across requests → preservable |

Worth a dev-mode warning for a reactive class whose root carries no authored id, so
the degradation is visible rather than silent.

### #1022 / #1027 — the fan-out double build

A different pipeline. Both regions are in the client's manifest, and `TodoList` is
nested inside `Shell`. Dirty a key they both react to:

```text
manifest: [ {id: "shell", type: shell},  {id: "todos", type: todo_list} ]
dirtied:  {"todos"}

walk_manifest -> both survive the filter pass
  _build_pass renders "shell"  -> descends -> TodoList.load() + render   (1)
  _build_pass renders "todos"  -> TodoList.load() + render               (2)
  _drop_nested  -> prunes the "todos" candidate from the OOB output

net: one wasted load + render + registry write, every request
```

The skip gate cannot help: `TodoList` **is** dirty — that is why it is a candidate.
Avoiding the redundant build needs containment knowledge *before* the build pass,
which the design deliberately declines to record. PR #1025 quiets the resulting
registry collision; #1027 is the follow-up that would skip the build.

### The handler's return always loads

Everything beneath the returned component is gated. The returned component itself is
not — you asked for it.

```python
@app.post("/todos")
async def add_todo():
    dirty("todos")
    return Shell.load(view="home")   # Shell.load() runs, Shell's template renders
                                     # children preserved, TodoList swapped OOB
```

Both narrower returns avoid even that:

```python
return TodoList.load(todos="home")   # primary = just the changed island
return None                          # primary = ""; fan-out ships OOB legs alone,
                                     # _fan_out sets HX-Reswap: none
```

Framework limit, or authoring choice? The latter — returning the shell when only a
region changed is asking for the shell.
