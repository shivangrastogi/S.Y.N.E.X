# Demo plugin

Minimal example of an AERIS community plugin.

## Layout

```
data/plugins/<name>/
    skill.py     # one or more @skill-decorated handlers
    README.md    # optional docs
    <anything>.py  # optional helper modules — import via `from . import helper`
```

## Lifecycle

1. Drop the folder in `data/plugins/<name>/`
2. Say **"enable plugin demo"** (or whatever the folder name is)
3. AERIS imports `skill.py`; the `@skill` decorators register handlers
4. Brain routes matching voice/text input to your handler

## Authoring tips

- Use the same `@skill(name=..., patterns=[...])` decorator as built-ins
- Plugins run in the main process, so you have full access to `core.*`
- Heavy deps should `try: import` and fail gracefully
- Plugins stay dormant until enabled — keep destructive logic behind a
  confirmation
