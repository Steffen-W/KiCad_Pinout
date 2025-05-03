import sys
import wx
import pprint
import re
import configparser
from pathlib import Path
import logging
import os

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)d]: %(message)s",
    filename="plugin.log",
    filemode="w",
)

try:
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        version = "python{}.{}".format(sys.version_info.major, sys.version_info.minor)
        venv_site_packages = os.path.join(venv, "lib", version, "site-packages")

        if venv_site_packages in sys.path:
            sys.path.remove(venv_site_packages)

        sys.path.insert(0, venv_site_packages)

    import wx
    from kipy import KiCad, errors, board
    from kipy.proto.common.types.base_types_pb2 import DocumentType
except Exception as e:
    logging.exception("Import Module")


# Try to import the KiCad manager
try:
    if __name__ == "__main__":
        from GUI import GUI_Dialog
        from kicad_manager import KiCadBoardManager
    else:
        from .GUI import GUI_Dialog
        from .kicad_manager import KiCadBoardManager
except ImportError:
    logging.error("Failed to import KiCadBoardManager")

# For backwards compatibility, try to import pcbnew directly
try:
    import pcbnew
except ImportError:
    pcbnew = None

logging.info("The plugin has been loaded successfully.")

FORMATS = {
    "c_define": {
        "start_seq": "// {reference} {value}",
        "pin_seq": "#define {pin_function} {netname}",
        "end_seq": "//",
    },
    "python": {},
    "markdown": {
        "start_seq": """Pinout for {reference}
        
| Pin number    | Pin name      | Pin net       |
|---------------|---------------|---------------|""",
        "pin_seq": "| {number}\t\t| {pin_function}\t\t| {netname}\t\t|",
        "end_seq": "",
    },
    "html": {
        "start_seq": """<p>Pinout for {reference}</p> <table><tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>""",
        "pin_seq": "<tr><td>{number}</td><td>{pin_function}</td><td>{netname}</td></tr>",
        "end_seq": "</table>",
    },
}


def read_ini(file_path):
    """
    Reads an INI file and converts it to a Python dictionary.

    :param file_path: Path to the INI file (str or Path object).
    :return: A dictionary with the INI file content.
    """
    config = configparser.ConfigParser()
    config.read(file_path)

    result = {}
    for section in config.sections():
        result[section] = {}
        for key, value in config.items(section):
            # Convert escaped newlines back to actual newlines
            if isinstance(value, str) and "\\n" in value:
                value = value.replace("\\n", "\n")
            result[section][key] = value

    return result


def write_ini(file_path, data):
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
    with file_path.open("w") as file:
        config.write(file)


def validate_format_string(format_string: str, placeholders: list):
    """
    Validates that all placeholders in the format string are allowed by placeholders.

    Args:
        format_string (str): The format string to validate.
        placeholders (list): A list of valid placeholder names.
    """

    # Find all placeholders in the format string using a regex
    placeholders_in_string = re.findall(r"\{(\w+)\}", format_string)

    # Check if any placeholders are not in the allowed list
    unexpected_placeholders = [
        placeholder
        for placeholder in placeholders_in_string
        if placeholder not in placeholders
    ]
    if unexpected_placeholders:
        return f"The format string contains unexpected placeholders: {', '.join(unexpected_placeholders)}"
    return ""


def format_pins(data, start_seq, pin_seq, end_seq):
    output = []
    for item in data:
        # Start
        error = validate_format_string(start_seq, ["reference", "value", "description"])
        if error:
            logging.error(f"Validation Error: {error}")
        else:
            output.append(
                start_seq.format(
                    reference=item["reference"],
                    value=item["value"],
                    description=item["description"],
                )
            )

        # Main
        error = validate_format_string(
            pin_seq, ["pin_function", "netname", "number", "pin_type", "connected"]
        )
        if error:
            logging.error(f"Validation Error: {error}")
        else:
            for pin in item["pins"]:
                output.append(
                    pin_seq.format(
                        pin_function=pin.get("pin_function", ""),
                        netname=pin.get("netname", ""),
                        number=pin.get("number", ""),
                        pin_type=pin.get("pin_type", ""),
                        connected=pin.get("connected", False),
                    )
                )

        # End
        error = validate_format_string(end_seq, ["reference", "value", "description"])
        if error:
            logging.error(f"Validation Error: {error}")
        else:
            output.append(
                end_seq.format(
                    reference=item["reference"],
                    value=item["value"],
                    description=item["description"],
                )
            )

    return "\n".join(output)


class KiCad_Pinout(GUI_Dialog):

    def __init__(self, manager=None):
        super(KiCad_Pinout, self).__init__(None)
        self.Bind(wx.EVT_MENU, self.on_escape, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_press)

        self.manager = manager or KiCadBoardManager()

        self.output_format.Bind(wx.EVT_CHOICE, self.update)

        ini_path = Path(__file__).parent / "options.ini"
        if not ini_path.exists():
            write_ini(ini_path, FORMATS)
            logging.debug(f"Created {ini_path}")

        try:
            config = read_ini(ini_path)
            if config:
                globals()["FORMATS"] = config
        except Exception as e:
            logging.error(f"Error reading options.ini: {e}")

        self.output_format.Set(list(FORMATS.keys()))
        self.output_format.SetSelection(0)

        self.change_format()
        self.update()

    def update(self, event=None):
        sel_type = self.output_format.GetStringSelection()
        logging.debug("change_format", "sel_type", sel_type)

        footprint_list = []

        # Ensure connection to KiCad
        if self.manager.connect():
            # Using the manager to get footprints
            for footprint in self.manager.get_selected_footprints():
                Value = self.manager.get_footprint_value(footprint)
                Reference = self.manager.get_footprint_reference(footprint)
                description = self.manager.get_footprint_description(footprint)
                pins = self.manager.get_pins(footprint)

                if not pins:
                    continue

                footprint_list.append(
                    {
                        "value": Value,
                        "reference": Reference,
                        "description": description,
                        "pins": pins,
                    }
                )
        pptext = pprint.pformat(footprint_list)
        logging.debug("footprint_list", pptext)

        start_seq = self.m_text_start.GetValue()
        pin_seq = self.m_text_pin.GetValue()
        end_seq = self.m_text_end.GetValue()

        if not len(footprint_list):
            formatted_output = "You have to mark components on the board."
        elif sel_type == "python":
            formatted_output = pptext
        else:
            formatted_output = format_pins(footprint_list, start_seq, pin_seq, end_seq)

        self.result.Clear()
        self.result.WriteText(formatted_output)

        if event:
            event.Skip()

    def change_format(self, event=None):
        sel_type = self.output_format.GetStringSelection()
        logging.debug("change_format", "sel_type", sel_type)

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

    def on_escape(self, event):
        self.Close()

    def on_key_press(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()


class ActionKiCadPlugin:
    """
    Action plugin that works with either pcbnew or kicad IPC
    """

    def defaults(self):
        self.name = "Pinout Generator"
        self.category = "Read PCB"
        self.description = "Generates pinout exports from the PCB nets"
        self.show_toolbar_button = True
        icon_path = Path(__file__).parent / "icon.png"
        self.icon_file_name = str(icon_path)
        self.dark_icon_file_name = str(icon_path)

        # Detect if we're in a pcbnew environment
        if "pcbnew" in sys.modules:
            import pcbnew

            self.__class__ = type(
                "ActionKiCadPlugin", (self.__class__, pcbnew.ActionPlugin), {}
            )
            pcbnew.ActionPlugin.__init__(self)

            if pcbnew.GetBoard() is None:
                logging.debug(f"pcbnew GetBoard fail")

    def Run(self):
        # Create and pass the KiCadBoardManager
        manager = KiCadBoardManager()
        Plugin_h = KiCad_Pinout(manager)
        Plugin_h.ShowModal()
        Plugin_h.Destroy()


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="KiCad Plugin")
    manager = KiCadBoardManager()
    KiCadPlugin_t = KiCad_Pinout(manager)
    KiCadPlugin_t.ShowModal()
    KiCadPlugin_t.Destroy()
