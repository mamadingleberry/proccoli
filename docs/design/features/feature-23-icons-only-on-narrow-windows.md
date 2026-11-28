# Feature 23: Icons Only on narrow windows

Plan: [plan/features/feature-23-icons-only-on-narrow-windows.md](../../plan/features/feature-23-icons-only-on-narrow-windows.md)


*[PLAN.md, Feature 23](../../plan/features/feature-23-icons-only-on-narrow-windows.md).* Proposed (B with C): the window's width picks how the
sidebar shows; the user's choice is never overwritten.

```mermaid
flowchart TB
    W["window width"] --> F{"≥ 780 sp?"}
    F -- yes --> U["the user's mode:<br/>Full · Icons Only · Hidden"]
    F -- no --> N{"≥ 400 sp?"}
    N -- yes --> I["Full → icons only, beside the content<br/>Icons Only → as chosen<br/>Hidden → hidden"]
    N -- no --> O["overlay, closed until asked<br/>(today's behaviour, below 780 sp)"]
    U & I & O --> M["menu marks the user's mode<br/>(+ a note when folded away)"]
```

- `sidebar_style.effective_layout(width, mode)` is pure; the window only
  applies it, and `SidebarVisibility` never saves a style the width chose.
