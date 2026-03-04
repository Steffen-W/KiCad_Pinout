import logging
import re
from typing import Any


# Check if the traditional KiCad API is available
def has_pcbnew() -> bool:
    try:
        import pcbnew

        logging.info("load pcbnew")
        return True
    except ImportError:
        logging.error("ImportError pcbnew")
        return False


# Check if the newer KiCad IPC API is available
def has_ipc() -> bool:
    try:
        from kipy import KiCad

        logging.info("load kipy")
        return True
    except ImportError:
        logging.error("ImportError kipy")
        return False


def connect_kicad() -> Any | None:
    try:
        from kipy import KiCad

        kicad = KiCad()
        kicad.get_version()
        return kicad
    except Exception as e:
        logging.error("Not connected to KiCad: %s", e)
        return None


def get_pad_type_name(pad_type_value: int) -> str:
    """Converts a PadType enum value to its string name."""
    pad_type_map = {
        0: "PT_UNKNOWN",
        1: "PT_PTH",  # Plated Through Hole
        2: "PT_SMD",  # Surface Mount Device
        3: "PT_EDGE_CONNECTOR",
        4: "PT_NPTH",  # Non-Plated Through Hole
    }
    return pad_type_map.get(pad_type_value, f"UNKNOWN_{pad_type_value}")


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
    """Converts KiCad pin/net names to valid C identifiers.
    ~{CS} -> NOT_CS, V_{A} -> V_A, spaces -> _
    """
    name = re.sub(r"~\{([^}]+)\}", r"NOT_\1", name)
    name = name.replace("{", "").replace("}", "").replace(" ", "_")
    return name


def vector2_to_mm(vector: Any) -> tuple[float, float]:
    return (vector.x / 1000000, vector.y / 1000000)


class KiCadBoardManager:
    """
    A wrapper class to handle both the traditional pcbnew API and the newer kipy API
    depending on what's available on the system.
    """

    def __init__(self, prefer_pcbnew: bool = True) -> None:
        """
        Initialize KiCad Board Manager

        Args:
            prefer_pcbnew: If True (default), prefer pcbnew API over IPC API when both are available.
                          This is recommended as pcbnew has more complete pad information (pin_function, pin_type).
        """
        self.prefer_pcbnew = prefer_pcbnew
        self.using_ipc = has_ipc()
        self.using_pcbnew = has_pcbnew()

        if not (self.using_pcbnew or self.using_ipc):
            raise ImportError("No KiCad API available.")

        self.pcbnew_board: Any | None = None
        self.ipc_board: Any | None = None

    def connect(self) -> bool:
        """Connect to the appropriate KiCad API"""
        logging.info(
            "connect: IPC %s pcbnew %s (prefer_pcbnew=%s)",
            self.using_ipc,
            self.using_pcbnew,
            self.prefer_pcbnew,
        )

        # Try pcbnew first if available and preferred
        if self.using_pcbnew and (self.prefer_pcbnew or not self.using_ipc):
            import pcbnew

            self.pcbnew_board = pcbnew.GetBoard()
            if self.pcbnew_board:
                logging.info("Connected via pcbnew API (has pin_function support)")
                # If pcbnew works and is preferred, don't use IPC
                if self.prefer_pcbnew:
                    self.using_ipc = False
                return True
            self.using_pcbnew = False
            logging.error("pcbnew.GetBoard fail")

        # Fall back to IPC if pcbnew failed or is not preferred
        if self.using_ipc:
            kicad = connect_kicad()
            if kicad is None:
                self.using_ipc = False
                logging.error("kicad connect fail")
            else:
                self.ipc_board = kicad.get_board()
                if self.ipc_board is not None:
                    logging.info(
                        "Connected via IPC API (pin_function not yet available)"
                    )
                    return True
                self.using_ipc = False
                logging.error("kicad.get_board fail")

        logging.error("No KiCad API could be connected")
        return False

    def get_selected_footprints(self) -> list[Any]:
        """Get selected footprints from the board"""
        if self.using_pcbnew and self.pcbnew_board:
            return [fp for fp in self.pcbnew_board.GetFootprints() if fp.IsSelected()]
        if self.using_ipc and self.ipc_board:
            from kipy.proto.common.types.enums_pb2 import KiCadObjectType

            return list(
                self.ipc_board.get_selection(types=(KiCadObjectType.KOT_PCB_FOOTPRINT,))
            )
        return []

    def get_footprint_properties(self, footprint: Any) -> dict[str, Any]:
        """Get all properties of a footprint"""
        properties: dict[str, Any] = {}

        if self.using_pcbnew:
            properties["value"] = footprint.GetValue()
            properties["reference"] = footprint.GetReference()
            properties["description"] = ""  # pcbnew API might not expose this directly
        elif self.using_ipc:
            from kipy.board_types import Field, FootprintInstance

            fp: FootprintInstance = footprint
            properties["value"] = fp.value_field.text.value
            properties["reference"] = fp.reference_field.text.value
            properties["description"] = fp.description_field.text.value
            properties["position"] = vector2_to_mm(fp.position)
            properties["orientation"] = fp.orientation
            properties["layer"] = fp.layer
            properties["locked"] = fp.locked
            properties["datasheet"] = fp.datasheet_field.text.value
            properties["not_in_schematic"] = fp.attributes.not_in_schematic
            properties["exclude_from_bill_of_materials"] = (
                fp.attributes.exclude_from_bill_of_materials
            )
            properties["exclude_from_position_files"] = (
                fp.attributes.exclude_from_position_files
            )
            properties["do_not_populate"] = fp.attributes.do_not_populate
            properties["mounting_style"] = fp.attributes.mounting_style
            properties["mpn"] = ""
            for item in fp.texts_and_fields:
                if (
                    isinstance(item, Field)
                    and len(item.text.value)
                    and item.name == "MPN"
                ):
                    properties["mpn"] = item.text.value

        return properties

    def get_pins(
        self, footprint: Any, clean_names: bool = True
    ) -> list[dict[str, Any]]:
        """Get pins from a footprint"""
        pins: list[dict[str, Any]] = []

        def clean_id(s: str) -> str:
            return _clean_identifier(s) if clean_names else s

        def clean_net(s: str) -> str:
            return _clean_netname(s) if clean_names else s

        if self.using_pcbnew:
            import pcbnew

            seen_numbers: set[str] = set()

            for pad in footprint.Pads():
                if isinstance(pad, pcbnew.PAD):
                    number = pad.GetNumber()
                    if number in seen_numbers:
                        continue
                    seen_numbers.add(number)

                    pins.append(
                        {
                            "number": number,
                            "pin_function": clean_id(pad.GetPinFunction()),
                            "pin_type": pad.GetPinType(),
                            "netname": clean_net(pad.GetNetname()),
                            "connected": ("no_connect" not in pad.GetPinType())
                            and pad.IsConnected(),
                            "position": (None, None),
                        }
                    )

        elif self.using_ipc:
            from kipy.board_types import FootprintInstance

            footprint_: FootprintInstance = footprint
            all_pads = footprint_.definition.pads
            for pad in all_pads:
                pins.append(
                    {
                        "number": pad.number,
                        # pad.pin_function available from KiCad 10 (kicad#22360)
                        "pin_function": clean_id(
                            getattr(pad, "pin_function", None)
                            or "pin_" + str(pad.number)
                        ),
                        "pin_type": get_pad_type_name(pad.pad_type),
                        "netname": clean_net(pad.net.name if pad.net else ""),
                        "connected": bool(pad.net and pad.net.name),
                        "position": vector2_to_mm(pad.position),
                    }
                )

        return pins
