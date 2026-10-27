---
name: game-design-doc
description: Write a concise, buildable game design document and backlog - pillars, core loop, mechanics, content tables, scope tiers, and acceptance criteria. Use before large builds or when scope is fuzzy.
---

# GDD template (keep to 2-4 pages)

1. **Pitch** (1-2 sentences) + genre + platform + target session length.
2. **Pillars** (max 3) - decisions are judged against them.
3. **Core loop**: act -> feedback -> reward -> new choice (text diagram). Minute-to-minute / level / meta.
4. **Controls** (keyboard, gamepad).
5. **Mechanics**: rules, numbers, edge cases. Enemies/items in tables (name, HP, speed, behaviour, drop).
6. **Progression & difficulty curve**; fail state; checkpoints.
7. **Content plan**: levels (teach/test/twist), bosses, UI screens.
8. **Art & audio direction**: resolution, palette, references, music mood.
9. **Scope tiers**: MUST (playable slice) / SHOULD / COULD / WON'T.
10. **Backlog** with S/M/L estimates and testable acceptance criteria.

Write to `docs/GDD.md`; keep tuning values in data resources, not prose.
