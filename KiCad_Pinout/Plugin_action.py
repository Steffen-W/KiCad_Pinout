import pcbnew
import os
import wx
import pprint
import re
import configparser

if __name__ == "__main__":
    from GUI import GUI_Dialog
else:
    from .GUI import GUI_Dialog

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
        "start_seq": """<p>Pinout for {reference}</p>
<table>
	<tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>
""",
        "pin_seq": "	<tr><td>{number}</td><td>{pin_function}</td><td>{netname}</td></tr>",
        "end_seq": "</table>",
    },
}


def read_ini(file_path):
    """
    Reads an INI file and converts it to a Python dictionary.

    :param file_path: Path to the INI file.
    :return: A dictionary with the INI file content.
    """
    config = configparser.ConfigParser()
    config.read(file_path)
    return {section: dict(config.items(section)) for section in config.sections()}


def write_ini(file_path, data):
    """
    Writes a Python dictionary into an INI file.

    :param file_path: Path to the INI file.
    :param data: A dictionary containing the INI content.
    """
    config = configparser.ConfigParser()
    for section, values in data.items():
        config[section] = values
    with open(file_path, "w") as file:
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
            print(f"Validation Error: {error}")
        else:
            output.append(
                start_seq.format(
                    reference=item["Reference"],
                    value=item["Value"],
                    description=item["description"],
                )
            )

        # Main
        error = validate_format_string(
            pin_seq, ["pin_function", "netname", "number", "pin_type", "connected"]
        )
        if error:
            print(f"Validation Error: {error}")
        else:
            for pin in item["pins"]:
                output.append(
                    pin_seq.format(
                        pin_function=pin.get("PinFunction", ""),
                        netname=pin.get("Netname", ""),
                        number=pin.get("Number", ""),
                        pin_type=pin.get("PinType", ""),
                        connected=pin.get("Connected", False),
                    )
                )

        # End
        error = validate_format_string(end_seq, ["reference", "value", "description"])
        if error:
            print(f"Validation Error: {error}")
        else:
            output.append(
                end_seq.format(
                    veference=item["Reference"],
                    value=item["Value"],
                    description=item["description"],
                )
            )

    return "\n".join(output)


def get_pins(component: pcbnew.FOOTPRINT):
    pinout = []
    seen_numbers = set()  # to avoid duplicates
    for pad in component.Pads():
        if isinstance(pad, pcbnew.PAD):
            number = pad.GetNumber()
            if number in seen_numbers:
                continue
            else:
                seen_numbers.add(number)

            pinout.append(
                {
                    "Number": number,
                    "PinFunction": pad.GetPinFunction(),
                    "PinType": pad.GetPinType(),
                    "Netname": pad.GetNetname(),
                    "Connected": ("no_connect" not in pad.GetPinType())
                    and pad.IsConnected(),
                }
            )
    return pinout


class KiCad_Pinout(GUI_Dialog):

    def __init__(self, board: pcbnew.BOARD, action: pcbnew.ActionPlugin):
        super(KiCad_Pinout, self).__init__(None)
        self.Bind(wx.EVT_MENU, self.on_escape, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_press)

        self.board = board
        self.action = action
        self.config = {}  # todo

        self.output_format.Bind(wx.EVT_CHOICE, self.update)
        # self.pinNameCB.Bind(wx.EVT_CHECKBOX, self.update)
        # self.pinNameFilter.Bind(wx.EVT_TEXT, self.update)

        # write_ini("options.ini", FORMATS)
        # config = read_ini("options.ini")
        # print(config)

        self.output_format.Set(list(FORMATS.keys()))
        self.output_format.SetSelection(0)

        start_seq = "// {reference} {value}"
        pin_seq = "#define {pin_function} {netname}"
        end_seq = "//"
        self.m_text_start.Clear()
        self.m_text_start.WriteText(start_seq)
        self.m_text_pin.Clear()
        self.m_text_pin.WriteText(pin_seq)
        self.m_text_end.Clear()
        self.m_text_end.WriteText(end_seq)

        self.update()

    def update(self, event=None):
        sel_type = self.output_format.GetStringSelection()
        print("change_format", "sel_type", sel_type)

        footprint_list = []
        for footprint in self.board.GetFootprints():
            if isinstance(footprint, pcbnew.FOOTPRINT):
                if footprint.IsSelected():

                    Value = footprint.GetValue()  # like ESP32-S2FH4
                    Reference = footprint.GetReference()  # like IC1
                    description = ""  # footprint.GetLibDescription()
                    pins = get_pins(footprint)

                    if not pins:
                        continue

                    footprint_list.append(
                        {
                            "Value": Value,
                            "Reference": Reference,
                            "description": description,
                            "pins": pins,
                        }
                    )
        pptext = pprint.pformat(footprint_list)
        print(pptext)

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
        print("change_format", "sel_type", sel_type)

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


class ActionKiCadPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Pinout Generator"
        self.category = "Read PCB"
        self.description = "Generates pinout exports from the PCB nets"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")
        self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    def Run(self):
        board = pcbnew.GetBoard()
        Plugin_h = KiCad_Pinout(board, self)
        Plugin_h.ShowModal()
        Plugin_h.Destroy()


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, title="KiCad Plugin")
    KiCadPlugin_t = KiCad_Pinout(None, None)
    KiCadPlugin_t.ShowModal()
    KiCadPlugin_t.Destroy()
