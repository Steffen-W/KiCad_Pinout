# KiCadPinout – Development Notes

## Code Quality

### Workflow

```bash
# Before commit
mypy . --strict
ruff check --fix --unsafe-fixes  && ruff format
pylint KiCadPinout/
```

### Tools

| Tool | Purpose | Status |
|------|---------|--------|
| ruff | Linting + Formatting | ✅ configured |
| mypy | Type Checking | ✅ 0 errors |
| pylint | Comprehensive analysis | ✅ 10/10 |
| bandit | Security (optional, weekly) | configured |

Config files: `ruff.toml`, `.pylintrc`, `mypy.ini`, `pyproject.toml`

**Excluded:** `gui.py` (wxFormBuilder-generated), `test/old_code_*`

---

## Plugin Structure (KiCad 9+)

```
KiCadPinout/
├── metadata.json       # PCM metadata (does NOT load the plugin)
├── __init__.py         # Entry point – supports both old and new system
└── KiCadPinout/
    ├── plugin_action.py
    ├── kicad_manager.py
    └── gui.py          # generated – do not edit manually
```

Plugin directory (Linux): `~/.local/share/kicad/9.0/3rdparty/plugins/`

### API Detection

```python
# kicad_manager.py connect() logs:
# INFO - connect: IPC False pcbnew True (prefer_pcbnew=True)
```

`pin_function` is only available via pcbnew, not via IPC.

### Troubleshooting

```bash
# Clear cache if plugin fails to load
rm -rf ~/.local/share/kicad/9.0/3rdparty/plugins/com.github.Steffen-W.KiCadPinout/__pycache__

# Check log
tail -f ~/.local/share/kicad/9.0/logs/kicad.log
```
