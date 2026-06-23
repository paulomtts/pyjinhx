# Gallery

The builtins, rendered by pyjinhx at docs build time (PJXLazyLoad needs a backend, so it sits this page out). Click through to the [guide](guide/builtins.md) for props and DOM contracts.

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

### [PJXTable](guide/builtins.md#pjxtable)
<!-- demo: PJXTable -->

```html
<PJXTable caption="Team members" striped="true" bordered="horizontal">
  <PJXTableHead>
    <PJXTableRow>
      <PJXTableHeaderCell sortable="true" sort="asc">Name</PJXTableHeaderCell>
      <PJXTableHeaderCell>Role</PJXTableHeaderCell>
    </PJXTableRow>
  </PJXTableHead>
  <PJXTableBody>
    <PJXTableRow selectable="true" value="1"><PJXTableCell>Ada Lovelace</PJXTableCell><PJXTableCell>Engineer</PJXTableCell></PJXTableRow>
    <PJXTableRow selectable="true" value="2"><PJXTableCell>Alan Turing</PJXTableCell><PJXTableCell>Researcher</PJXTableCell></PJXTableRow>
  </PJXTableBody>
</PJXTable>
```

## Overlays & dialogs

### [PJXModal](guide/builtins.md#pjxmodal)
<!-- demo: PJXModal -->

```html
<PJXModal id="demo-modal">
  <PJXModalHeader id="demo-modal-h" title="Confirm changes"/>
  <PJXModalBody id="demo-modal-b">Your draft will be published immediately. This action cannot be undone.</PJXModalBody>
  <PJXModalFooter id="demo-modal-f"><button class="pjx-demo-btn" data-pjx-close>Cancel</button></PJXModalFooter>
</PJXModal>
```

### [PJXDrawer](guide/builtins.md#pjxdrawer)
<!-- demo: PJXDrawer -->

```html
<PJXDrawer id="demo-drawer" side="right">
  <PJXDrawerHeader id="demo-drawer-h" title="Filter results"/>
  <PJXDrawerBody id="demo-drawer-b"><p>Adjust filters to narrow down your results.</p></PJXDrawerBody>
  <PJXDrawerFooter id="demo-drawer-f"><button class="pjx-demo-btn" data-pjx-close>Done</button></PJXDrawerFooter>
</PJXDrawer>
```

### [PJXConfirmDialog](guide/builtins.md#pjxconfirmdialog)
<!-- demo: PJXConfirmDialog -->

```html
<PJXConfirmDialog id="demo-confirm"/>
```

### [PJXPromptDialog](guide/builtins.md#pjxpromptdialog)
<!-- demo: PJXPromptDialog -->

```html
<PJXPromptDialog id="demo-prompt"/>
```

### [PJXNotification](guide/builtins.md#pjxnotification)
<!-- demo: PJXNotification -->

```html
<PJXNotification
  id="demo-notification"
  content="Your changes have been saved."
  corner="top-right"
  timeout="4000"/>
```

### [PJXAlert](guide/builtins.md#pjxalert)
<!-- demo: PJXAlert -->

```html
<PJXAlert variant="info" title="Heads up" body="A new version is available."/>
```

### [PJXTooltip](guide/builtins.md#pjxtooltip)
<!-- demo: PJXTooltip -->

```html
<PJXTooltip id="demo-tooltip" placement="top">
  <PJXTooltipTrigger id="demo-tooltip-tr">Hover over me</PJXTooltipTrigger>
  <PJXTooltipContent id="demo-tooltip-tc">This is additional context shown on hover or focus.</PJXTooltipContent>
</PJXTooltip>
```

### [PJXPopover](guide/builtins.md#pjxpopover)
<!-- demo: PJXPopover -->

```html
<PJXPopover id="demo-popover">
  <PJXPopoverTrigger id="demo-popover-t" role="dialog">Show info</PJXPopoverTrigger>
  <PJXPopoverPanel id="demo-popover-p" role="dialog"><strong>Keyboard shortcuts</strong><p style="margin:.35rem 0 0">Press <kbd>?</kbd> anytime to reopen this panel.</p></PJXPopoverPanel>
</PJXPopover>
```

## Interaction & loading

### [PJXDropdown](guide/builtins.md#pjxdropdown)
<!-- demo: PJXDropdown -->

```html
<PJXDropdown trigger="Actions" menu_label="Actions menu">
  <button>Edit</button>
  <button>Duplicate</button>
  <button>Delete</button>
</PJXDropdown>
```

### [PJXTabGroup](guide/builtins.md#pjxtabgroup)
<!-- demo: PJXTabGroup -->

```html
<PJXTabGroup>
  <PJXTabList>
    <PJXTab id="tg-t0" panel="tg-p0" selected="true">Overview</PJXTab>
    <PJXTab id="tg-t1" panel="tg-p1">Activity</PJXTab>
    <PJXTab id="tg-t2" panel="tg-p2" closeable="true">Settings</PJXTab>
  </PJXTabList>
  <PJXTabPanel id="tg-p0" tab="tg-t0"><p>Project summary and key metrics.</p></PJXTabPanel>
  <PJXTabPanel id="tg-p1" tab="tg-t1"><p>Recent commits and deploys.</p></PJXTabPanel>
  <PJXTabPanel id="tg-p2" tab="tg-t2"><p>Repository configuration.</p></PJXTabPanel>
</PJXTabGroup>
```

### [PJXResizableGroup](guide/builtins.md#pjxresizablegroup)
<!-- demo: PJXResizableGroup -->

```html
<PJXResizableGroup direction="row">
  <PJXResizablePanel size="25" min="15">sidebar</PJXResizablePanel>
  <PJXResizableHandle/>
  <PJXResizablePanel size="75">main</PJXResizablePanel>
</PJXResizableGroup>
```

### [PJXToastHost](guide/builtins.md#pjxtoasthost)
<!-- demo: PJXToastHost -->

```html
<PJXToastHost position="bottom-right"/>
```

### [PJXRegionLoader](guide/builtins.md#pjxregionloader)
<!-- demo: PJXRegionLoader -->

```html
<PJXRegionLoader id="demo-region"/>
```

### [PJXPageLoader](guide/builtins.md#pjxpageloader)
<!-- demo: PJXPageLoader -->

```html
<PJXPageLoader id="demo-page-loader"/>
```

## Form controls

### [PJXChipInput](guide/builtins.md#pjxchipinput)
<!-- demo: PJXChipInput -->

```html
<PJXChipInput name="tags" values='["python", "jinja2", "htmx"]' placeholder="Add tag…"/>
```

### [PJXFormField](guide/builtins.md#pjxformfield)
<!-- demo: PJXFormField -->

```html
<PJXFormField label="Email address" for_id="demo-email" help="We'll never share your email with anyone." required="true">
  <input id="demo-email" type="email" name="email" placeholder="you@example.com">
</PJXFormField>
```

### [PJXToggleSwitch](guide/builtins.md#pjxtoggleswitch)
<!-- demo: PJXToggleSwitch -->

```html
<PJXToggleSwitch name="notifications" checked="true" label="Email notifications"/>
```

### [PJXSegmentedControl](guide/builtins.md#pjxsegmentedcontrol)
<!-- demo: PJXSegmentedControl -->

```html
<PJXSegmentedControl name="view" options='[["list", "List"], ["grid", "Grid"], ["table", "Table"]]' selected="grid"/>
```

### [PJXPasswordInput](guide/builtins.md#pjxpasswordinput)
<!-- demo: PJXPasswordInput -->

```html
<PJXPasswordInput name="password" placeholder="Enter your password" autocomplete="current-password" required="true"/>
```

### [PJXPaginator](guide/builtins.md#pjxpaginator)
<!-- demo: PJXPaginator -->

```html
<PJXPaginator page="4" total_pages="12" url="/items?page={page}"/>
```
