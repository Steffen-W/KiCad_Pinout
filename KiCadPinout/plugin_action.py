import configparser
import logging
import os
import pprint
import re
import sys
from pathlib import Path
from typing import Any

try:
    import wx

    if __name__ == "__main__":
        from gui import PinoutDialog
    else:
        from .gui import PinoutDialog

    _has_wx = True
except ImportError:
    _has_wx = False

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)d]: %(message)s",
        filename=Path(__file__).resolve().parent / "plugin.log",
        filemode="w",
    )

try:
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        venv_site_packages = os.path.join(venv, "lib", py_version, "site-packages")

        if venv_site_packages in sys.path:
            sys.path.remove(venv_site_packages)

        sys.path.insert(0, venv_site_packages)
except Exception:
    logging.exception("Import Module")


if __name__ == "__main__":
    from kicad_manager import KiCadBoardManager
else:
    from .kicad_manager import KiCadBoardManager

logging.info("The plugin has been loaded successfully.")

FORMATS: dict[str, dict[str, str]] = {
    "c_define": {
        "start_seq": "// {reference} {value}\n",
        "pin_seq": "#define {pin_function} {netname}\n",
        "end_seq": "\n",
    },
    "python": {},
    "markdown": {
        "start_seq": """Pinout for {reference}\n\n| Pin number    | Pin name      | Pin net       |\n|---------------|---------------|---------------|\n""",
        "pin_seq": "| {number}\t\t| {pin_function}\t\t| {netname}\t\t|\n",
        "end_seq": "\n",
    },
    "html": {
        "start_seq": """<p>Pinout for {reference}</p>\n<table>\n\t<tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>\n""",
        "pin_seq": "\t<tr><td>{number}</td><td>{pin_function}</td><td>{netname}</td></tr>\n",
        "end_seq": "</table>\n",
    },
    "list": {
        "start_seq": "",
        "pin_seq": "{number}\t{pin_function}\t{netname}\n",
        "end_seq": "\n",
    },
    "csv": {
        "start_seq": "",
        "pin_seq": '"{number}","{pin_function}","{netname}"\n',
        "end_seq": "\n",
    },
    "c_enum": {
        "start_seq": "enum pinout_{reference} {{\n",
        "pin_seq": "\tpin_{netname} = {pin_function},\n",
        "end_seq": "}};\n",
    },
    "python_dict": {
        "start_seq": "pinout_{reference} = {{\n",
        "pin_seq": "\t'pin_{netname}' : '{pin_function}',\n",
        "end_seq": "}}\n",
    },
}


def read_ini(file_path: Path | str) -> dict[str, dict[str, str]]:
    """
    Reads an INI file and converts it to a Python dictionary.

    :param file_path: Path to the INI file (str or Path object).
    :return: A dictionary with the INI file content.
    """
    config = configparser.ConfigParser()
    config.read(file_path)

    result: dict[str, dict[str, str]] = {}
    for section in config.sections():
        result[section] = {}
        for key, value in config.items(section):
            # Convert escaped newlines back to actual newlines
            if isinstance(value, str) and "\\n" in value:
                value = value.replace("\\n", "\n")
            result[section][key] = value

    return result


def write_ini(file_path: Path | str, data: dict[str, dict[str, str]]) -> None:
    """
    Writes a Python dictionary into an INI file.

    :param file_path: Path to the INI file (str or Path object).
    :param data: A dictionary containing the INI content.
    """
    config = configparser.ConfigParser()
    for section, values in data.items():
        config[section] = {}
        for key, value in values.items():
            # Convert multi-line strings to properly formatted INI entries
            if isinstance(value, str) and "\n" in value:
                value = value.replace("\n", "\\n")
            config[section][key] = value

    # Convert to Path object if it's not already
    file_path = Path(file_path)
    with file_path.open("w", encoding="utf-8") as file:
        config.write(file)


def validate_format_string(format_string: str, item: dict[str, Any]) -> str:
    """
    Validates that all placeholders in the format string are available in the given item.

    Args:
        format_string (str): The format string to validate.
        item (dict): The dictionary containing available keys.
    """

    # Find all placeholders in the format string using a regex
    placeholders_in_string = re.findall(r"\{(\w+)\}", format_string)

    # Check if any placeholders are not available in the item
    available_keys = list(item.keys())

    unexpected_placeholders = [
        placeholder
        for placeholder in placeholders_in_string
        if placeholder not in available_keys
    ]
    if unexpected_placeholders:
        return f"The format string contains unavailable placeholders: {', '.join(unexpected_placeholders)}"
    return ""


def _apply_template(template: str, context: dict[str, Any]) -> str | None:
    """Validates and formats a template string. Returns None on validation error."""
    error = validate_format_string(template, context)
    if error:
        logging.error("Validation Error: %s", error)
        return None
    placeholders = re.findall(r"\{(\w+)\}", template)
    return template.format(**{p: context.get(p, "") for p in placeholders})


def format_pins(
    data: list[dict[str, Any]], start_seq: str, pin_seq: str, end_seq: str
) -> str:
    output = []
    for item in data:
        if (result := _apply_template(start_seq, item)) is not None:
            output.append(result)

        if item["pins"]:
            pin_context = {**item["pins"][0], **item}
            if not validate_format_string(pin_seq, pin_context):
                for pin in item["pins"]:
                    context = {**item, **pin}
                    placeholders = re.findall(r"\{(\w+)\}", pin_seq)
                    output.append(
                        pin_seq.format(**{p: context.get(p, "") for p in placeholders})
                    )

        if (result := _apply_template(end_seq, item)) is not None:
            output.append(result)

    return "".join(output)


class KiCadPinout(PinoutDialog):  # type: ignore[misc]
    def __init__(self, manager: KiCadBoardManager | None = None) -> None:
        super().__init__(None)
        self.Bind(wx.EVT_MENU, self.on_escape, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_press)

        self.manager = manager or KiCadBoardManager()

        self.output_format.Bind(wx.EVT_CHOICE, self.update)

        ini_path = Path(__file__).parent / "options.ini"
        if not ini_path.exists():
            write_ini(ini_path, FORMATS)
            logging.debug("Created %s", ini_path)

        try:
            config = read_ini(ini_path)
            if config:
                for section, values in config.items():
                    if section not in FORMATS:
                        FORMATS[section] = values
        except Exception as e:
            logging.error("Error reading options.ini: %s", e)

        self.output_format.Set(list(FORMATS.keys()))
        self.output_format.SetSelection(0)

        self.change_format()
        self.update()

    def update(self, event: wx.Event | None = None) -> None:
        sel_type = self.output_format.GetStringSelection()
        logging.debug("sel_type %s", sel_type)

        footprint_list: list[dict[str, Any]] = []

        # Ensure connection to KiCad
        if self.manager.connect():
            # Using the manager to get footprints
            for footprint in self.manager.get_selected_footprints():
                properties = self.manager.get_footprint_properties(footprint)
                pins = self.manager.get_pins(footprint)

                if not pins:
                    continue

                footprint_data = {"pins": pins, **properties}
                footprint_list.append(footprint_data)
        pptext = pprint.pformat(footprint_list)
        logging.debug("footprint_list: %s", pptext)

        start_seq = self.m_text_start.GetValue()
        pin_seq = self.m_text_pin.GetValue()
        end_seq = self.m_text_end.GetValue()

        if not footprint_list:
            formatted_output = "You have to mark components on the board."
        elif sel_type == "python":
            formatted_output = pptext
        else:
            formatted_output = format_pins(footprint_list, start_seq, pin_seq, end_seq)

        self.result.Clear()
        self.result.WriteText(formatted_output)

        if event:
            event.Skip()

    def change_format(self, event: wx.Event | None = None) -> None:
        sel_type = self.output_format.GetStringSelection()
        logging.debug("sel_type %s", sel_type)

        if "start_seq" in FORMATS[sel_type]:
            self.m_text_start.SetValue(FORMATS[sel_type]["start_seq"])
            self.m_text_pin.SetValue(FORMATS[sel_type]["pin_seq"])
            self.m_text_end.SetValue(FORMATS[sel_type]["end_seq"])
        else:
            self.m_text_start.SetValue("")
            self.m_text_pin.SetValue("")
            self.m_text_end.SetValue("")

        self.update()

        if event:
            event.Skip()

    def on_escape(self, event: wx.Event) -> None:
        self.Close()

    def on_key_press(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()


if __name__ == "__main__":
    _app = wx.App()
    _frame = wx.Frame(None, title="KiCad Plugin")
    _plugin = KiCadPinout(KiCadBoardManager())
    _plugin.ShowModal()
    _plugin.Destroy()
