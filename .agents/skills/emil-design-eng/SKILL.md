---
name: emil-design-eng
description: This skill encodes Emil Kowalski's philosophy on UI polish, component design, animation decisions, and the invisible details that make software feel great.
---

# Design Engineering (Emil Kowalski)

## Core Philosophy
1. **Taste is trained, not innate**: Reverse-engineer great work. Inspect details and curves.
2. **Unseen details compound**: When everything functions as intended with subtle tactile feedback, the aggregate produces an interface people love.
3. **Beauty is leverage**: Good defaults, custom curves, and micro-interactions make software stand out.

## Review Format (Required)
Always use markdown comparison tables:
| Before | After | Why |
| --- | --- | --- |

## Animation & Motion Rules
- **Active state physics**: `transform: scale(0.97)` on `:active` for all pressables.
- **Never animate from `scale(0)`**: Start from `scale(0.95); opacity: 0`.
- **Custom Easing**:
  - `--ease-out: cubic-bezier(0.23, 1, 0.32, 1);`
  - `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);`
  - `--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);`
- **Never use `ease-in`**: It feels sluggish. Always use `ease-out` for UI entrances.
- **Fast durations**: 100-160ms for button press; 150-250ms for popovers/dropdowns; 200-300ms for modals.
- **Origin-aware popovers**: Transform-origin should be anchored to triggers.
