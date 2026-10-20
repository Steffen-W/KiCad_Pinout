"""Pinout dialog. Run as script, this is the IPC plugin entry point (plugin.json);
the pcbnew action plugin (../__init__.py) opens the same dialog.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import pprint
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

if __name__ == "__main__":
    from gui import PinoutDialog
    from kicad_manager import Footprint, field_key, read_ipc
else:
    from .gui import PinoutDialog
    from .kicad_manager import Footprint, field_key

if not logging.getLogger().handlers:
    # own file per variant: pcbnew loads its plugin at startup and would
    # otherwise overwrite the log of the last IPC run
    log_name = "plugin_ipc.log" if __name__ == "__main__" else "plugin.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)d]: %(message)s",
        filename=Path(__file__).resolve().parent / log_name,
        filemode="w",
    )

INI_PATH = Path(__file__).parent / "options.ini"
STATE_PATH = Path(__file__).parent / "state.json"  # last settings of the dialog

FORMATS: dict[str, dict[str, str]] = {
    "c_define": {
        "start_seq": "// {reference} {value}\n",
        "pin_seq": '#define {pin_function} "{netname}"\n',
        "end_seq": "\n",
    },
    "python": {},
    "markdown": {
        "start_seq": "## {reference} ({value})\n\n| Pin | Name | Net |\n|---------------|---------------|---------------|\n",
        "pin_seq": "| {number}\t\t| {pin_function}\t\t| {netname}\t\t|\n",
        "end_seq": "\n",
    },
    "html": {
        "start_seq": """<p>Pinout for {reference}</p>\n<table>\n\t<tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>\n""",
        "pin_seq": "\t<tr><td>{number}</td><td>{pin_function}</td><td>{netname}</td></tr>\n",
        "end_seq": "</table>\n",
    },
    "list": {
        "start_seq": "{reference} {value}\n",
        "pin_seq": "{number}\t{pin_function}\t{netname}\n",
        "end_seq": "\n",
    },
    "csv": {
        "start_seq": "number,name,net\n",
        "pin_seq": '"{number}","{pin_function}","{netname}"\n',
        "end_seq": "\n",
    },
    "c_enum": {
        "start_seq": "enum pinout_{reference} {{\n",
        "pin_seq": "\tpin_{pin_function} = {number},\n",
        "end_seq": "}};\n",
    },
    "python_dict": {
        "start_seq": "pinout_{reference} = {{\n",
        "pin_seq": "\t'{pin_function}' : '{netname}',\n",
        "end_seq": "}}\n",
    },
}


def read_ini(file_path: Path) -> dict[str, dict[str, str]]:
    config = configparser.ConfigParser(interpolation=None)  # templates may contain %
    config.read(file_path, encoding="utf-8")
    return {  # values are single-line: \n and \t stand for line breaks and tabs
        section: {
            key: value.replace("\\n", "\n").replace("\\t", "\t")
            for key, value in config.items(section)
        }
        for section in config.sections()
    }


# Written once for new installs; built-in formats are not copied into it, so
# their improvements reach existing installs.
INI_TEMPLATE = """\
# Own output formats. A section named like a built-in format (c_define,
# markdown, html, list, csv, c_enum, python_dict) overrides only the values
# given; other names add a format. Write line breaks as \\n, tabs as \\t.
#
# [my_format]
# start_seq = {reference} {lcsc_part}\\n
# pin_seq = {number}\\t{pin_function}\\t{netname}\\n
# end_seq = \\n
"""

# Defaults that older versions copied into options.ini; not user changes
_OLD_DEFAULTS = {("c_define", "pin_seq"): "#define {pin_function} {netname}\n"}


def _is_default(name: str, key: str, value: str) -> bool:
    # compared stripped: older versions lost leading tabs when writing the file
    defaults = (FORMATS.get(name, {}).get(key), _OLD_DEFAULTS.get((name, key)))
    return any(d is not None and value.strip() == d.strip() for d in defaults)


def load_formats() -> tuple[dict[str, dict[str, str]], str]:
    """Built-in formats, extended by options.ini (per value, so a section may
    override only pin_seq), and a warning if options.ini could not be used."""
    try:
        if not INI_PATH.exists():
            INI_PATH.write_text(INI_TEMPLATE, encoding="utf-8")
            logging.debug("Created %s", INI_PATH)
        formats = {name: dict(values) for name, values in FORMATS.items()}
        for name, values in read_ini(INI_PATH).items():
            changed = {k: v for k, v in values.items() if not _is_default(name, k, v)}
            formats.setdefault(name, {}).update(changed)
        return formats, ""
    except Exception as e:
        logging.exception("Cannot use %s", INI_PATH)
        return FORMATS, f"{INI_PATH} ignored, using built-in formats: {e}\n\n"


def load_state() -> dict[str, Any]:
    """Last dialog settings; "sequences" is always a dict of strings."""
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"sequences": {}}
    except Exception:
        logging.exception("Cannot read %s", STATE_PATH)
        return {"sequences": {}}
    if not isinstance(state, dict):
        return {"sequences": {}}
    sequences = state.get("sequences")
    state["sequences"] = (
        {k: v for k, v in sequences.items() if isinstance(v, str)}
        if isinstance(sequences, dict)
        else {}
    )
    return state


def save_state(state: dict[str, Any]) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        logging.exception("Cannot write %s", STATE_PATH)


def token_names(footprints: list[Footprint]) -> tuple[list[str], list[str]]:
    """Footprint and pin tokens of the given footprints, in order of appearance."""
    fp_keys = dict.fromkeys(k for fp in footprints for k in fp if k != "pins")
    pin_keys = dict.fromkeys(k for fp in footprints for pin in fp["pins"] for k in pin)
    return list(fp_keys), list(pin_keys)


class _Tokens(dict):  # type: ignore[type-arg]
    """Template values. {LCSC Part} also finds lcsc_part. A token that only other
    footprints have becomes empty; unknown tokens (typos) stay visible."""

    def __init__(self, values: dict[str, Any], known: set[str]) -> None:
        super().__init__(values)
        self.known = known

    def __missing__(self, key: str) -> Any:
        normalized = field_key(key)
        if normalized in self:
            return self[normalized]
        return "" if normalized in self.known else "{" + key + "}"


def fill(template: str, tokens: dict[str, Any], known: set[str]) -> str:
    try:
        return template.format_map(_Tokens(tokens, known))
    except Exception as e:  # e.g. unbalanced braces, {0}, {x.attr}
        return f"[template error in {template!r}: {e}]\n"


def format_pins(
    footprints: list[Footprint], start_seq: str, pin_seq: str, end_seq: str
) -> str:
    fp_keys, pin_keys = token_names(footprints)
    known_fp, known_pin = set(fp_keys), set(fp_keys + pin_keys)
    output = []
    for fp in footprints:
        output.append(fill(start_seq, fp, known_fp))
        output.extend(fill(pin_seq, {**fp, **pin}, known_pin) for pin in fp["pins"])
        output.append(fill(end_seq, fp, known_fp))
    return "".join(output)


def token_overview(footprints: list[Footprint]) -> str:
    """Available tokens with an example value each, shown by the ? button."""
    if not footprints:
        return "Select footprints on the board and press Update to see their tokens."
    fp_keys, pin_keys = token_names(footprints)
    pins = [pin for fp in footprints for pin in fp["pins"]]
    width = max(len(k) for k in fp_keys + pin_keys) + 4

    def lines(keys: list[str], items: list[dict[str, Any]]) -> list[str]:
        result = []
        for key in keys:
            example = next(
                (str(i[key]) for i in items if i.get(key) not in ("", None)), ""
            )
            example = example if len(example) <= 50 else example[:47] + "..."
            result.append(f"{{{key}}}".ljust(width) + example)
        return result

    return "\n".join(
        [
            "Footprint tokens (all sequences):",
            *lines(fp_keys, footprints),
            "",
            "Pin tokens (pin sequence only):",
            *lines(pin_keys, pins),
        ]
    )


class KiCadPinout(PinoutDialog):  # type: ignore[misc]
    def __init__(self, read_footprints: Callable[[bool], list[Footprint]]) -> None:
        super().__init__(None)
        self.read_footprints = read_footprints
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_press)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.m_checkCleanNames = wx.CheckBox(self, wx.ID_ANY, "Clean names")
        self.m_checkCleanNames.SetValue(True)
        self.m_checkCleanNames.Bind(wx.EVT_CHECKBOX, self.update)
        sizer = self.m_buttonUpdate.GetContainingSizer()
        sizer.Add(self.m_checkCleanNames, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        height = self.m_buttonUpdate.GetBestSize().height
        button_tokens = wx.Button(self, wx.ID_ANY, "?", size=(height, height))
        button_tokens.SetToolTip("Show all tokens of the selected footprints")
        button_tokens.Bind(wx.EVT_BUTTON, self.show_tokens)
        index = next(
            i
            for i, item in enumerate(sizer.GetChildren())
            if item.GetWindow() is self.m_buttonUpdate
        )
        sizer.Insert(index, button_tokens, 0, wx.ALL, 5)  # left of Update
        self.footprints: list[Footprint] = []

        # restore the last session: format, edited sequences, Clean names
        state = load_state()
        self.formats, self.warning = load_formats()
        names = list(self.formats)
        self.output_format.Set(names)
        if state.get("format") in names:
            self.output_format.SetSelection(names.index(state["format"]))
            fmt = {**self.formats[state["format"]], **state["sequences"]}
        else:
            self.output_format.SetSelection(0)
            fmt = self.formats[names[0]]
        self.m_checkCleanNames.SetValue(bool(state.get("clean_names", True)))
        self.set_sequences(fmt)

    def update(self, event: wx.Event | None = None) -> None:
        self.footprints = []  # no stale tokens if reading fails
        try:
            footprints = self.read_footprints(self.m_checkCleanNames.GetValue())
            self.footprints = footprints
            logging.debug("footprints: %s", pprint.pformat(footprints))
            if not footprints:
                text = "Select footprints with pads on the board, then press Update."
            elif self.output_format.GetStringSelection() == "python":
                text = pprint.pformat(footprints)
            else:
                text = format_pins(
                    footprints,
                    self.m_text_start.GetValue(),
                    self.m_text_pin.GetValue(),
                    self.m_text_end.GetValue(),
                )
        except Exception as e:
            logging.exception("Reading the board failed")
            text = f"Reading the board failed: {e}"

        self.result.SetValue(self.warning + text)
        if event:
            event.Skip()

    def show_tokens(self, event: wx.Event) -> None:
        self.result.SetValue(
            token_overview(self.footprints) + "\n\nUpdate: back to output"
        )

    def sequence_fields(self) -> dict[str, wx.TextCtrl]:
        return {
            "start_seq": self.m_text_start,
            "pin_seq": self.m_text_pin,
            "end_seq": self.m_text_end,
        }

    def set_sequences(self, fmt: dict[str, str]) -> None:
        for name, text in self.sequence_fields().items():
            text.SetValue(fmt.get(name, ""))
        self.update()

    def change_format(self, event: wx.Event | None = None) -> None:
        self.set_sequences(self.formats[self.output_format.GetStringSelection()])
        if event:
            event.Skip()

    def on_close(self, event: wx.CloseEvent) -> None:
        # only edits: unchanged sequences follow later changes of the format
        name = self.output_format.GetStringSelection()
        fmt = self.formats[name]
        save_state(
            {
                "format": name,
                "sequences": {
                    key: text.GetValue()
                    for key, text in self.sequence_fields().items()
                    if text.GetValue() != fmt.get(key, "")
                },
                "clean_names": self.m_checkCleanNames.GetValue(),
            }
        )
        event.Skip()

    def on_key_press(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()


def _prefer_venv_packages() -> None:
    """Search the plugin's virtual environment before KiCad's own packages."""
    venv = os.environ.get("VIRTUAL_ENV")
    if not venv:
        return
    import sysconfig

    layout = "nt" if os.name == "nt" else "posix_prefix"
    site_packages = sysconfig.get_path(
        "purelib", layout, vars={"base": venv, "platbase": venv}
    )
    if site_packages in sys.path:
        sys.path.remove(site_packages)
    sys.path.insert(0, site_packages)


def main() -> None:
    logging.debug(
        "IPC plugin started: pid %s, %s, socket %s",
        os.getpid(),
        sys.executable,
        os.environ.get("KICAD_API_SOCKET"),
    )
    _prefer_venv_packages()  # before read_ipc() imports kipy
    _app = wx.App()
    with KiCadPinout(read_ipc) as dialog:
        dialog.ShowModal()
    logging.debug("IPC plugin closed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("IPC plugin failed")
        raise
