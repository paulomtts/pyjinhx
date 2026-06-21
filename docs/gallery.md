# Gallery

The builtins, rendered by pyjinhx at docs build time (PJXLazyPanel needs a backend, so it sits this page out). Click through to the [guide](guide/builtins.md) for props and DOM contracts.

## Static

### [PJXBadge](guide/builtins.md#pjxbadge)
<!-- demo: PJXBadge -->

```html
<PJXBadge label="Active" color="brand"/>
```

### [PJXCard](guide/builtins.md#pjxcard)
<!-- demo: PJXCard -->

```html
<PJXCard>
  <PJXCardHeader title="Quarterly report"/>
  <PJXCardBody>Revenue grew 12% over Q1.</PJXCardBody>
  <PJXCardFooter>Updated today</PJXCardFooter>
</PJXCard>
```

### [PJXDivider](guide/builtins.md#pjxdivider)
<!-- demo: PJXDivider -->

```html
<PJXDivider orientation="horizontal" label="or continue with"/>
```

### [PJXSpinner](guide/builtins.md#pjxspinner)
<!-- demo: PJXSpinner -->

```html
<PJXSpinner size="sm" label="Loading data"/>
```

### [PJXAvatar](guide/builtins.md#pjxavatar)
<!-- demo: PJXAvatar -->

```html
<PJXAvatar initials="JD" size="sm" alt="Jane Doe"/>
```

### [PJXAvatarStack](guide/builtins.md#pjxavatarstack)
<!-- demo: PJXAvatarStack -->

```html
<PJXAvatarStack extra_count="4">
  <PJXAvatar initials="AB" size="sm" alt="Alice Brown"/>
  <PJXAvatar initials="CD" size="sm" alt="Carol Davis"/>
  <PJXAvatar initials="EF" size="sm" alt="Eve Foster"/>
</PJXAvatarStack>
```

### [PJXBreadcrumb](guide/builtins.md#pjxbreadcrumb)
<!-- demo: PJXBreadcrumb -->

```html
<PJXBreadcrumb items='[["Home","/"],["Projects","/projects"],["Dashboard",null]]'/>
```

### [PJXSkeleton](guide/builtins.md#pjxskeleton)
<!-- demo: PJXSkeleton -->

```html
<PJXSkeleton variant="text" lines="3"/>
```

### [PJXProgress](guide/builtins.md#pjxprogress)
<!-- demo: PJXProgress -->

```html
<PJXProgress value="65" max="100" label="Upload progress"/>
```

### [PJXEmptyState](guide/builtins.md#pjxemptystate)
<!-- demo: PJXEmptyState -->

```html
<PJXEmptyState>
  <h3>No results</h3>
  <p>Try a different search term.</p>
</PJXEmptyState>
```

### [PJXIcon](guide/builtins.md#pjxicon)
<!-- demo: PJXIcon -->

```html
<PJXIcon name="plus" size="24" label="Add"/>
```

### [PJXButton](guide/builtins.md#pjxbutton)
<!-- demo: PJXButton -->

```html
<PJXButton content="Save" variant="primary"/>
```

### [PJXAccordion](guide/builtins.md#pjxaccordion)
<!-- demo: PJXAccordion -->

```html
<PJXAccordion>
  <PJXAccordionTrigger>What is pyjinhx?</PJXAccordionTrigger>
  <PJXAccordionContent><p>A Python/Jinja HTML component framework.</p></PJXAccordionContent>
</PJXAccordion>
```

### [PJXAccordionGroup](guide/builtins.md#pjxaccordiongroup)
<!-- demo: PJXAccordionGroup -->

```html
<PJXAccordionGroup mode="exclusive" gap="0.25rem">
  <PJXAccordion>
    <PJXAccordionTrigger>Section A</PJXAccordionTrigger>
    <PJXAccordionContent><p>Content A.</p></PJXAccordionContent>
  </PJXAccordion>
  <PJXAccordion open="False">
    <PJXAccordionTrigger>Section B</PJXAccordionTrigger>
    <PJXAccordionContent><p>Content B.</p></PJXAccordionContent>
  </PJXAccordion>
</PJXAccordionGroup>
```

## Overlays & dialogs

### [PJXModal](guide/builtins.md#pjxmodal)
<!-- demo: PJXModal -->

### [PJXDrawer](guide/builtins.md#pjxdrawer)
<!-- demo: PJXDrawer -->

### [PJXConfirmDialog](guide/builtins.md#pjxconfirmdialog)
<!-- demo: PJXConfirmDialog -->

### [PJXPromptDialog](guide/builtins.md#pjxpromptdialog)
<!-- demo: PJXPromptDialog -->

### [PJXNotification](guide/builtins.md#pjxnotification)
<!-- demo: PJXNotification -->

### [PJXAlert](guide/builtins.md#pjxalert)
<!-- demo: PJXAlert -->

### [PJXTooltip](guide/builtins.md#pjxtooltip)
<!-- demo: PJXTooltip -->

### [PJXPopover](guide/builtins.md#pjxpopover)
<!-- demo: PJXPopover -->

## Interaction & loading

### [PJXDropdown](guide/builtins.md#pjxdropdown)
<!-- demo: PJXDropdown -->

### [PJXTabGroup](guide/builtins.md#pjxtabgroup)
<!-- demo: PJXTabGroup -->

### [PJXPanel](guide/builtins.md#pjxpanel)
<!-- demo: PJXPanel -->

### [PJXResizableGroup](guide/builtins.md#pjxresizablegroup)
<!-- demo: PJXResizableGroup -->

### [PJXToastHost](guide/builtins.md#pjxtoasthost)
<!-- demo: PJXToastHost -->

### [PJXRegionLoader](guide/builtins.md#pjxregionloader)
<!-- demo: PJXRegionLoader -->

### [PJXPageLoader](guide/builtins.md#pjxpageloader)
<!-- demo: PJXPageLoader -->

## Form controls

### [PJXChipInput](guide/builtins.md#pjxchipinput)
<!-- demo: PJXChipInput -->

### [PJXFormField](guide/builtins.md#pjxformfield)
<!-- demo: PJXFormField -->

### [PJXToggleSwitch](guide/builtins.md#pjxtoggleswitch)
<!-- demo: PJXToggleSwitch -->

### [PJXSegmentedControl](guide/builtins.md#pjxsegmentedcontrol)
<!-- demo: PJXSegmentedControl -->

### [PJXPasswordInput](guide/builtins.md#pjxpasswordinput)
<!-- demo: PJXPasswordInput -->
