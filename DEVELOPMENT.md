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

### Entry points

- `__init__.py`: pcbnew action plugin, reads the board with `read_pcbnew()`
- `KiCadPinout/plugin_action.py` run as script (`plugin.json`): IPC plugin, reads with `read_ipc()`

`pin_function`/`pin_type` via IPC need KiCad 10 (`symbol_pin` in the pad proto); KiCad 9 leaves them empty ("Clean names" then gives `PIN_<number>`).

The plugin identifier in `plugin.json` must match KiCad's regex
`^[a-zA-Z]{2,}(\.([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]|[a-zA-Z0-9])){2,}$`, so no underscores.
Otherwise KiCad silently ignores the IPC plugin.

### Troubleshooting

```bash
# Clear cache if plugin fails to load
rm -rf ~/.local/share/kicad/9.0/3rdparty/plugins/com.github.Steffen-W.KiCadPinout/__pycache__

# Check log
tail -f ~/.local/share/kicad/9.0/logs/kicad.log
```
