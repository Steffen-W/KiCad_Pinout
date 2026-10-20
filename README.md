![Static Badge](https://img.shields.io/badge/Supports_KiCad-v6%2C_v7%2C_v8%2C_v9-%23314cb0)
![Static Badge](https://img.shields.io/badge/Supports-Windows%2C_Mac%2C_Linux-Green)

[![GitHub Release](https://img.shields.io/github/release/Steffen-W/Import-LIB-KiCad-Plugin.svg)](https://github.com/Steffen-W/Import-LIB-KiCad-Plugin/releases/latest)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Steffen-W/KiCadPinout/total)](https://github.com/Steffen-W/KiCadPinout/releases/latest/download/KiCadPinout.zip)

# KiCad Pinout Generator

A KiCad plugin that generates formatted pinout documentation from PCB components. Supports both the pcbnew API (KiCad 6+) and the IPC API (KiCad 9+), allowing seamless operation across different KiCad versions.

## Features

- Automatically extracts pin information from selected components on your PCB
- Generates pinout documentation in multiple formats:
  - C-style defines
  - Markdown tables
  - HTML tables
  - Python data structures
- Customizable output templates via options.ini
- Simple and intuitive GUI interface

## Installation

### Using Plugin and Content Manager

Requires KiCad 9 or newer. On older versions, install the plugin manually.

1. Open KiCad
2. Go to PCB Editor
3. Click on `Tools` → `Plugin and Content Manager`
4. Search for "Pinout Generator"
5. Click `Install`

## Standalone

The GUI can be launched directly for development and testing:

```bash
python KiCadPinout/plugin_action.py
```

## Usage

1. Open your PCB in KiCad PCB Editor
2. Select one or more components on your board
3. Go to `Tools` → `Pinout Generator`
4. Choose your desired output format
5. Customize the output templates if needed
6. The generated pinout documentation will appear in the text area
7. Copy the result or save it to a file

## Output Formats

The plugin supports the following output formats:

Examples for an LED `D15` with "Clean names" enabled (the default): `Net-(D15-1)` becomes `NET_D15-1`, `/LC` becomes `LC`, and pin names become valid C identifiers (`IO0/TXD` -> `IO0_TXD`, `3V3` -> `PIN_3V3`, `+`/`D-` -> `PLUS`/`D_MINUS`, no name -> `PIN_<number>`, equal names get the pad number: `GND_1`, `GND_2`). Net names, references and other fields are not turned into identifiers, so `c_define` writes the net as a string and `c_enum` needs numeric pad numbers.

### C-style defines

```c
// D15 USB
#define GA "NET_D15-1"
#define GK "LC"
#define RA "LC"
#define RK "NET_D15-1"
```

### Markdown

```markdown
## D15 (USB)

| Pin | Name | Net |
|---------------|---------------|---------------|
| 1		| GA		| NET_D15-1		|
| 2		| GK		| LC		|
| 3		| RA		| LC		|
| 4		| RK		| NET_D15-1		|
```

### HTML

```html
<p>Pinout for D15</p>
<table>
	<tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>
	<tr><td>1</td><td>GA</td><td>NET_D15-1</td></tr>
	<tr><td>2</td><td>GK</td><td>LC</td></tr>
	<tr><td>3</td><td>RA</td><td>LC</td></tr>
	<tr><td>4</td><td>RK</td><td>NET_D15-1</td></tr>
</table>
```

### Python

Shows the raw footprint and pin data, including custom fields such as `lcsc_part`.
`pin_type` is the electrical type of the symbol pin. The example is shortened; all tokens are listed under [Available placeholders](#customization).

```python
[
    {
        "datasheet": "",
        "description": "",
        "lcsc_part": "C2827693",
        "pins": [
            {
                "connected": True,
                "netname": "NET_D15-1",
                "number": "1",
                "pin_function": "GA",
                "pin_type": "passive",
            },
            {
                "connected": True,
                "netname": "LC",
                "number": "2",
                "pin_function": "GK",
                "pin_type": "passive",
            },
            {
                "connected": True,
                "netname": "LC",
                "number": "3",
                "pin_function": "RA",
                "pin_type": "passive",
            },
            {
                "connected": True,
                "netname": "NET_D15-1",
                "number": "4",
                "pin_function": "RK",
                "pin_type": "passive",
            },
        ],
        "reference": "D15",
        "value": "USB",
    }
]
```

## Customization

The output formats can be customized by editing the `options.ini` file located in the plugin directory. The file is created with a commented example the first time you run the plugin. Values in it override the built-in format of the same name one by one (a `[markdown]` section with only `pin_seq` keeps the built-in header and footer), new sections add formats. Write line breaks as `\n` and tabs as `\t`.

The dialog remembers the last selected format, the edited sequences and "Clean names" in `state.json` next to `options.ini`. Selecting a format in the list loads its sequences again.

Each format has three template sections:
- `start_seq`: The beginning of the output (e.g., table header)
- `pin_seq`: The format for each pin entry
- `end_seq`: The ending of the output (e.g., table footer)

Available placeholders:
- For start/end: `{reference}`, `{value}`, `{description}`, `{footprint}` (`Resistor_SMD:R_0402_1005Metric`), `{footprint_library}`, `{footprint_name}` and every other footprint field
  - Placement: `{side}` (`top`/`bottom`), `{x_mm}`, `{y_mm}`, `{x_mil}`, `{y_mil}`, `{rotation}` (degrees)
  - Attributes: `{mounting}` (`smd`/`through_hole`/`unspecified`), `{dnp}`, `{exclude_from_bom}`, `{exclude_from_pos_files}`, `{board_only}`, `{locked}` (`True`/`False`)
- For pins: `{number}`, `{pin_function}`, `{netname}`, `{pin_type}`, `{connected}`, `{net_class}`, `{pad_type}` (`smd`/`pth`/`npth`/`connector`), `{pad_x_mm}`, `{pad_y_mm}`, `{pad_x_mil}`, `{pad_y_mil}` (plus all footprint fields)

Positions are relative to the drill/place origin, with y pointing down as in the PCB editor.

Custom fields are named in snake_case: the field `LCSC Part` becomes `{lcsc_part}`, `MPN` becomes `{mpn}`.
Writing the field name as in KiCad (`{LCSC Part}`) works too. The `?` button next to `Update` lists all tokens of the selected footprints with an example value in the result field, ready to copy; `Update` shows the output again. A field that only some of the selected footprints have stays empty for the others.
Unknown placeholders are left in the output unchanged, so typos are easy to spot.

## Compatibility

- KiCad 6.0+: "Pinout Generator (pcbnew)" button (pcbnew API)
- KiCad 9.0+: "Pinout Generator" button (IPC API); pin names and types via IPC need KiCad 10
- Tested on Windows, Linux, and macOS

## Requirements

- Python 3.9+
- wxPython
- kicad-python (IPC plugin, KiCad 9+)
- KiCad 6.0 or higher

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.