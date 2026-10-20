"""Reads the selected footprints from KiCad, via pcbnew (SWIG) or the IPC API.

Both readers return the same structure: one dict per footprint holding all of
its fields (e.g. "LCSC Part" -> "lcsc_part") plus a "pins" list.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

Footprint = dict[str, Any]

_NOT_IN_C_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]")
_SIGNS = {"+": "PLUS", "-": "MINUS"}

# Names pcbnew's PAD.GetPinType() uses where they differ from the IPC enum
_IPC_PIN_TYPES = {
    "tristate": "tri_state",
    "power_input": "power_in",
    "power_output": "power_out",
}


def field_key(name: str) -> str:
    """Turns a field name into a template token: 'LCSC Part' -> 'lcsc_part'."""
    return re.sub(r"\W+", "_", name).strip("_").lower()


def natural_sort_key(s: str) -> list[int | str]:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def _clean_netname(netname: str) -> str:
    """Normalizes KiCad net names for readable output.
    unconnected-(...) -> NC, Net-(J1-Pin_1) -> NET_J1-Pin_1, /Sheet/sig -> Sheet_sig
    """
    if netname.startswith("unconnected-"):
        return "NC"
    if netname.startswith("Net-(") and netname.endswith(")"):
        return "NET_" + netname[5:-1]
    if netname.startswith("/"):
        return netname.replace("/", "_").replace(" ", "_").lstrip("_")
    return netname


def _clean_identifier(name: str) -> str:
    """Converts KiCad pin names to valid C identifiers.
    ~{CS} -> NOT_CS, V_{A} -> V_A, IO0/TXD -> IO0_TXD, 3V3 -> PIN_3V3,
    + -> PLUS, D- -> D_MINUS, +5V -> PLUS_5V
    """
    if name in _SIGNS:
        return _SIGNS[name]
    # a sign at the start or end is a polarity; inside it separates (IO0-TXD)
    name = re.sub(r"_?([+-])$", lambda m: "_" + _SIGNS[m[1]], name)
    name = re.sub(r"^([+-])_?", lambda m: _SIGNS[m[1]] + "_", name)
    name = re.sub(r"~\{([^}]+)\}", r"NOT_\1", name)
    name = _NOT_IN_C_IDENTIFIER.sub("_", name.replace("{", "").replace("}", ""))
    return "PIN_" + name if name[:1].isdigit() else name


def _number(value: float, decimals: int) -> str:
    """112.1550 -> '112.155', 180.0 -> '180', -0.0 -> '0'"""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _position(prefix: str, x: int, y: int, origin: tuple[int, int]) -> dict[str, str]:
    """Position in nm as {prefix}x_mm ... {prefix}y_mil, relative to the drill/place
    origin, y pointing down as in the PCB editor."""
    x, y = x - origin[0], y - origin[1]
    return {
        f"{prefix}x_mm": _number(x / 1e6, 4),
        f"{prefix}y_mm": _number(y / 1e6, 4),
        f"{prefix}x_mil": _number(x / 25400, 2),
        f"{prefix}y_mil": _number(y / 25400, 2),
    }


def _footprint(
    lib_id: str,
    properties: dict[str, Any],
    fields: dict[str, str],
    pins: list[dict[str, Any]],
    clean_names: bool,
) -> Footprint:
    unique: dict[str, dict[str, Any]] = {}
    for pin in pins:  # skip mechanical (unnumbered) and duplicate pads
        if pin["number"] and pin["number"] not in unique:
            unique[pin["number"]] = pin
    pins = sorted(unique.values(), key=lambda p: natural_sort_key(p["number"]))
    if clean_names:
        for pin in pins:
            function = pin["pin_function"] or f"PIN_{pin['number']}"
            pin["pin_function"] = _clean_identifier(function)
            pin["netname"] = _clean_netname(pin["netname"])
        # equal names (several GND pins, A/B and A-B) would break C output
        counts = Counter(pin["pin_function"] for pin in pins)
        for pin in pins:
            if counts[pin["pin_function"]] > 1:
                pin["pin_function"] += "_" + _NOT_IN_C_IDENTIFIER.sub(
                    "_", pin["number"]
                )
    library, _, name = lib_id.rpartition(":")
    footprint: Footprint = {
        "reference": "",
        "value": "",
        "description": "",
        "footprint": lib_id,  # Resistor_SMD:R_0402_1005Metric
        "footprint_library": library,
        "footprint_name": name,
        **properties,
    }
    footprint.update({field_key(name): text for name, text in fields.items()})
    footprint["pins"] = pins
    return footprint


def _sorted(footprints: list[Footprint]) -> list[Footprint]:
    footprints = [fp for fp in footprints if fp["pins"]]
    return sorted(footprints, key=lambda fp: natural_sort_key(fp["reference"]))


def _pcbnew_fields(fp: Any) -> dict[str, str]:
    """All fields of a footprint by canonical (untranslated) name."""
    try:
        fields = list(fp.GetFields())  # KiCad 8 and 10+
    except TypeError:  # KiCad 9 returns an unwrapped std::vector (kicad#19463)
        count, fields, field_id = fp.GetNextFieldId(), [], 0  # count = number of fields
        while len(fields) < count and field_id < 1000:  # ids can have gaps
            if field := fp.GetFieldById(field_id):
                fields.append(field)
            field_id += 1
    except AttributeError:  # before KiCad 8
        return {"Reference": fp.GetReference(), "Value": fp.GetValue()}
    # skip the Footprint field (KiCad 8+): {footprint} comes from the library ID,
    # as via IPC, which does not send this field
    return {
        f.GetCanonicalName(): f.GetText()
        for f in fields
        if f and f.GetCanonicalName() != "Footprint"
    }


def read_pcbnew(clean_names: bool = True) -> list[Footprint]:
    """Selected footprints of the board open in pcbnew (SWIG action plugin)."""
    import pcbnew

    board = pcbnew.GetBoard()
    aux_origin = board.GetDesignSettings().GetAuxOrigin()
    origin = (aux_origin.x, aux_origin.y)
    pad_types = {
        pcbnew.PAD_ATTRIB_PTH: "pth",
        pcbnew.PAD_ATTRIB_SMD: "smd",
        pcbnew.PAD_ATTRIB_CONN: "connector",
        pcbnew.PAD_ATTRIB_NPTH: "npth",
    }
    footprints = []
    for fp in board.GetFootprints():
        if not fp.IsSelected():
            continue
        pins = []
        for pad in fp.Pads():
            # "passive+no_connect" for a pin with no-connect flag; IPC sends a flag
            pin_type = pad.GetPinType()
            netname = pad.GetNetname()
            position = pad.GetPosition()
            pins.append(
                {
                    "number": pad.GetNumber(),
                    "pin_function": pad.GetPinFunction(),
                    "pin_type": pin_type.removesuffix("+no_connect"),
                    "netname": netname,
                    "connected": "no_connect" not in pin_type and pad.IsConnected(),
                    "net_class": pad.GetNetClassName() if netname else "",
                    "pad_type": pad_types.get(pad.GetAttribute(), "unknown"),
                    **_position("pad_", position.x, position.y, origin),
                }
            )
        attributes = fp.GetAttributes()
        if attributes & pcbnew.FP_SMD:
            mounting = "smd"
        elif attributes & pcbnew.FP_THROUGH_HOLE:
            mounting = "through_hole"
        else:
            mounting = "unspecified"
        position = fp.GetPosition()
        properties = {
            "side": "bottom" if fp.IsFlipped() else "top",
            **_position("", position.x, position.y, origin),
            "rotation": _number(fp.GetOrientationDegrees(), 2),
            "mounting": mounting,
            "dnp": bool(attributes & getattr(pcbnew, "FP_DNP", 0)),  # KiCad 8+
            "exclude_from_bom": bool(attributes & pcbnew.FP_EXCLUDE_FROM_BOM),
            "exclude_from_pos_files": bool(
                attributes & pcbnew.FP_EXCLUDE_FROM_POS_FILES
            ),
            "board_only": bool(attributes & pcbnew.FP_BOARD_ONLY),
            "locked": fp.IsLocked(),
        }
        lib_id = str(fp.GetFPIDAsString())
        footprints.append(
            _footprint(lib_id, properties, _pcbnew_fields(fp), pins, clean_names)
        )
    return _sorted(footprints)


def _ipc_pin_type(enum: Any, value: int) -> str:
    """'EPT_POWER_INPUT' -> 'power_in', as pcbnew names it."""
    try:
        name: str = enum.Name(value).removeprefix("EPT_").lower()
    except ValueError:  # sent by a KiCad newer than the installed kicad-python
        return f"unknown_{value}"
    return _IPC_PIN_TYPES.get(name, name)


def read_ipc(clean_names: bool = True) -> list[Footprint]:
    """Selected footprints of the board open in KiCad, via the IPC API (KiCad 9+)."""
    from kipy import KiCad, errors
    from kipy.board_types import Field, FootprintInstance
    from kipy.proto.board.board_commands_pb2 import BoardOriginType
    from kipy.proto.board.board_types_pb2 import (
        BoardLayer,
        FootprintMountingStyle,
        PadType,
    )
    from kipy.proto.common.types.base_types_pb2 import ElectricalPinType
    from kipy.proto.common.types.enums_pb2 import KiCadObjectType

    try:
        board = KiCad().get_board()
        items = board.get_selection(types=(KiCadObjectType.KOT_PCB_FOOTPRINT,))
        selection = [fp for fp in items if isinstance(fp, FootprintInstance)]
    except errors.ConnectionError as e:
        raise RuntimeError(
            "Could not connect to KiCad. Is the API server enabled"
            " (Preferences > Plugins)?"
        ) from e
    except errors.ApiError as e:
        if e.code == errors.ApiStatusCode.AS_BUSY:
            raise RuntimeError(
                "KiCad is busy (open dialog or running tool?), press Update again."
            ) from e
        raise RuntimeError(f"No PCB open in KiCad? ({e})") from e
    try:
        drill_origin = board.get_origin(BoardOriginType.BOT_DRILL)
        origin = (drill_origin.x, drill_origin.y)
    except errors.ApiError:  # older KiCad
        origin = (0, 0)
    nets = [
        pad.net
        for fp in selection
        for pad in fp.definition.pads
        if pad.net and pad.net.name
    ]
    try:
        net_classes = {
            net: net_class.name
            for net, net_class in board.get_netclass_for_nets(nets).items()
        }
    except errors.ApiError:  # older KiCad
        net_classes = {}
    mountings = {
        FootprintMountingStyle.FMS_SMD: "smd",
        FootprintMountingStyle.FMS_THROUGH_HOLE: "through_hole",
    }
    pad_types = {
        PadType.PT_PTH: "pth",
        PadType.PT_SMD: "smd",
        PadType.PT_EDGE_CONNECTOR: "connector",
        PadType.PT_NPTH: "npth",
    }
    footprints = []
    for fp in selection:
        fields = {
            f.name: f.text.value for f in fp.texts_and_fields if isinstance(f, Field)
        }
        pins = []
        for pad in fp.definition.pads:
            if pad.proto.HasField("symbol_pin"):  # sent by KiCad 10+
                symbol_pin = pad.proto.symbol_pin
                pin_function = symbol_pin.name
                pin_type = _ipc_pin_type(ElectricalPinType, symbol_pin.type)
                no_connect = symbol_pin.no_connect or pin_type == "no_connect"
            else:
                pin_function, pin_type, no_connect = "", "", False
            netname = pad.net.name if pad.net else ""
            pins.append(
                {
                    "number": pad.number,
                    "pin_function": pin_function,
                    "pin_type": pin_type,
                    "netname": netname,
                    "connected": bool(netname) and not no_connect,
                    "net_class": net_classes.get(netname, ""),
                    "pad_type": pad_types.get(pad.pad_type, "unknown"),
                    **_position("pad_", pad.position.x, pad.position.y, origin),
                }
            )
        attributes = fp.attributes
        properties = {
            "side": "bottom" if fp.layer == BoardLayer.BL_B_Cu else "top",
            **_position("", fp.position.x, fp.position.y, origin),
            "rotation": _number(fp.orientation.degrees, 2),
            "mounting": mountings.get(attributes.mounting_style, "unspecified"),
            "dnp": attributes.do_not_populate,
            "exclude_from_bom": attributes.exclude_from_bill_of_materials,
            "exclude_from_pos_files": attributes.exclude_from_position_files,
            "board_only": attributes.not_in_schematic,
            "locked": fp.locked,
        }
        lib_id = str(fp.definition.id)
        footprints.append(_footprint(lib_id, properties, fields, pins, clean_names))
    return _sorted(footprints)
