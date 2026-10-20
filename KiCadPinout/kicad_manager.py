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
    ~{CS} -> NOT_CS, V_{A} -> V_A, IO0/TXD -> IO0_TXD, 3V3 -> PIN_3V3
    """
    name = re.sub(r"~\{([^}]+)\}", r"NOT_\1", name)
    name = _NOT_IN_C_IDENTIFIER.sub("_", name.replace("{", "").replace("}", ""))
    return "PIN_" + name if name[:1].isdigit() else name


def _footprint(
    fields: dict[str, str], pins: list[dict[str, Any]], clean_names: bool
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
    footprint: Footprint = {"reference": "", "value": "", "description": ""}
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
    return {f.GetCanonicalName(): f.GetText() for f in fields if f}


def read_pcbnew(clean_names: bool = True) -> list[Footprint]:
    """Selected footprints of the board open in pcbnew (SWIG action plugin)."""
    import pcbnew

    footprints = []
    for fp in pcbnew.GetBoard().GetFootprints():
        if not fp.IsSelected():
            continue
        pins = []
        for pad in fp.Pads():
            # "passive+no_connect" for a pin with no-connect flag; IPC sends a flag
            pin_type = pad.GetPinType()
            pins.append(
                {
                    "number": pad.GetNumber(),
                    "pin_function": pad.GetPinFunction(),
                    "pin_type": pin_type.removesuffix("+no_connect"),
                    "netname": pad.GetNetname(),
                    "connected": "no_connect" not in pin_type and pad.IsConnected(),
                }
            )
        footprints.append(_footprint(_pcbnew_fields(fp), pins, clean_names))
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
    from kipy.board_types import Field
    from kipy.proto.common.types.base_types_pb2 import ElectricalPinType
    from kipy.proto.common.types.enums_pb2 import KiCadObjectType

    try:
        board = KiCad().get_board()
        selection = board.get_selection(types=(KiCadObjectType.KOT_PCB_FOOTPRINT,))
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
                }
            )
        footprints.append(_footprint(fields, pins, clean_names))
    return _sorted(footprints)
