![Static Badge](https://img.shields.io/badge/Supports_KiCad-v6%2C_v7%2C_v8%2C_v9-%23314cb0)
![Static Badge](https://img.shields.io/badge/Supports-Windows%2C_Mac%2C_Linux-Green)

[![GitHub Release](https://img.shields.io/github/release/Steffen-W/Import-LIB-KiCad-Plugin.svg)](https://github.com/Steffen-W/Import-LIB-KiCad-Plugin/releases/latest)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Steffen-W/KiCad_Pinout/total)](https://github.com/Steffen-W/KiCad_Pinout/releases/latest/download/KiCad_Pinout.zip)

# KiCad Pinout Generator

A KiCad plugin that generates formatted pinout documentation from PCB components. Supports both KiCad 6 (legacy API) and KiCad 9+ (new IPC API), allowing seamless operation across different KiCad versions.

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

1. Open KiCad
2. Go to PCB Editor
3. Click on `Tools` → `Plugin and Content Manager`
4. Search for "Pinout Generator"
5. Click `Install`

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

### C-style defines

```c
// D15 USB
#define GA Net-(D15-1)
#define GK /LC
#define RA /LC
#define RK Net-(D15-1)
//
```

### Markdown

```markdown
Pinout for D15
        
| Pin number | Pin name | Pin net     |
| ---------- | -------- | ----------- |
| 1          | GA       | Net-(D15-1) |
| 2          | GK       | /LC         |
| 3          | RA       | /LC         |
| 4          | RK       | Net-(D15-1) |
```

### HTML

```html
<p>Pinout for D15</p>
<table><tr><th>Pin number</th><th>Pin name</th><th>Pin net</th></tr>
<tr><td>1</td><td>GA</td><td>Net-(D15-1)</td></tr>
<tr><td>2</td><td>GK</td><td>/LC</td></tr>
<tr><td>3</td><td>RA</td><td>/LC</td></tr>
<tr><td>4</td><td>RK</td><td>Net-(D15-1)</td></tr>
</table>
```

### Python

```python
[{'description': '',
  'pins': [{'connected': True,
            'netname': 'Net-(D15-1)',
            'number': 1,
            'pin_function': 'GA',
            'pin_type': 'PT_SMD'},
           {'connected': True,
            'netname': '/LC',
            'number': 2,
            'pin_function': 'GK',
            'pin_type': 'PT_SMD'},
           {'connected': True,
            'netname': '/LC',
            'number': 3,
            'pin_function': 'RA',
            'pin_type': 'PT_SMD'},
           {'connected': True,
            'netname': 'Net-(D15-1)',
            'number': 4,
            'pin_function': 'RK',
            'pin_type': 'PT_SMD'}],
  'reference': 'D15',
  'value': 'USB'}]
```

## Customization

The output formats can be customized by editing the `options.ini` file located in the plugin directory. The file is automatically created the first time you run the plugin.

Each format has three template sections:
- `start_seq`: The beginning of the output (e.g., table header)
- `pin_seq`: The format for each pin entry
- `end_seq`: The ending of the output (e.g., table footer)

Available placeholders:
- For start/end: `{reference}`, `{value}`, `{description}`
- For pins: `{number}`, `{pin_function}`, `{netname}`, `{pin_type}`, `{connected}`

## Compatibility

- KiCad 6.0+ (using pcbnew API)
- KiCad 7.0+ (using either pcbnew API or IPC API)
- Tested on Windows, Linux, and macOS

## Requirements

- Python 3.6+
- wxPython
- numpy
- KiCad 6.0 or higher

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.