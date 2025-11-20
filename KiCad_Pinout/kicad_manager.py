import logging


# Check if the traditional KiCad API is available
def has_pcbnew():
    try:
        import pcbnew

        logging.info("load pcbnew")
        return True
    except ImportError:
        logging.error("ImportError pcbnew")
        return False


# Check if the newer KiCad IPC API is available
def has_IPC():
    try:
        from kipy import KiCad

        logging.info("load kipy")
        return True
    except ImportError:
        logging.error("ImportError kipy")
        return False


def connect_kicad():
    try:
        from kipy import KiCad

        kicad = KiCad()
        kicad.get_version()
        return kicad
    except BaseException as e:
        logging.error(f"Not connected to KiCad: {e}")
        return None


def get_pad_type_name(pad_type_value):  # only IPC
    """Konvertiert einen PadType-Enum-Wert in seinen Namen"""
    pad_type_map = {
        0: "PT_UNKNOWN",
        1: "PT_PTH",  # Plated Through Hole
        2: "PT_SMD",  # Surface Mount Device
        3: "PT_EDGE_CONNECTOR",
        4: "PT_NPTH",  # Non-Plated Through Hole
    }
    return pad_type_map.get(pad_type_value, f"UNKNOWN_{pad_type_value}")


def Vector2_to_mm(vector):
    return (vector.x / 1000000, vector.y / 1000000)


class KiCadBoardManager:
    """
    A wrapper class to handle both the traditional pcbnew API and the newer kipy API
    depending on what's available on the system.
    """

    def __init__(self, prefer_pcbnew=True):
        """
        Initialize KiCad Board Manager

        Args:
            prefer_pcbnew: If True (default), prefer pcbnew API over IPC API when both are available.
                          This is recommended as pcbnew has more complete pad information (pin_function, pin_type).
        """
        self.prefer_pcbnew = prefer_pcbnew
        self.using_IPC = has_IPC()
        self.using_pcbnew = has_pcbnew()

        if not (self.using_pcbnew or self.using_IPC):
            raise ImportError("No KiCad API available.")

        self.pcbnew_board = None
        self.kipy_kicad = None
        self.IPC_board = None

    def connect(self):
        """Connect to the appropriate KiCad API"""
        logging.info(
            f"connect: IPC {self.using_IPC} pcbnew {self.using_pcbnew} (prefer_pcbnew={self.prefer_pcbnew})"
        )

        # Try pcbnew first if available and preferred
        if self.using_pcbnew and (self.prefer_pcbnew or not self.using_IPC):
            import pcbnew

            self.pcbnew_board = pcbnew.GetBoard()
            if self.pcbnew_board:
                logging.info("Connected via pcbnew API (has pin_function support)")
                # If pcbnew works and is preferred, don't use IPC
                if self.prefer_pcbnew:
                    self.using_IPC = False
                return True
            else:
                self.using_pcbnew = False
                logging.error("pcbnew.GetBoard fail")

        # Fall back to IPC if pcbnew failed or is not preferred
        if self.using_IPC:

            kicad = connect_kicad()
            if kicad is None:
                self.using_IPC = False
                logging.error("kicad connect fail")
            else:
                self.IPC_board = kicad.get_board()
                if self.IPC_board is not None:
                    logging.info("Connected via IPC API (pin_function not yet available)")
                    return True
                else:
                    self.using_IPC = False
                    logging.error("kicad.get_board fail")

        logging.error("connect")
        return False

    def get_selected_footprints(self):
        """Get selected footprints from the board"""
        if self.using_pcbnew and self.pcbnew_board:
            return [fp for fp in self.pcbnew_board.GetFootprints() if fp.IsSelected()]
        elif self.using_IPC and self.IPC_board:
            from kipy.proto.common.types.enums_pb2 import KiCadObjectType

            return self.IPC_board.get_selection(types=(KiCadObjectType.KOT_PCB_FOOTPRINT,))
        return []

    def get_footprint_properties(self, footprint):
        """Get all properties of a footprint"""
        properties = {}

        if self.using_pcbnew:
            properties["value"] = footprint.GetValue()
            properties["reference"] = footprint.GetReference()
            properties["description"] = ""  # pcbnew API might not expose this directly
        elif self.using_IPC:
            from kipy.board_types import Field, FootprintInstance

            fp: FootprintInstance = footprint
            properties["value"] = fp.value_field.text.value
            properties["reference"] = fp.reference_field.text.value
            properties["description"] = fp.description_field.text.value
            properties["position"] = Vector2_to_mm(fp.position)
            properties["orientation"] = fp.orientation
            properties["layer"] = fp.layer
            properties["locked"] = fp.locked
            properties["datasheet"] = fp.datasheet_field.text.value
            properties["not_in_schematic"] = fp.attributes.not_in_schematic
            properties["exclude_from_bill_of_materials"] = (
                fp.attributes.exclude_from_bill_of_materials
            )
            properties["exclude_from_position_files"] = fp.attributes.exclude_from_position_files
            properties["do_not_populate"] = fp.attributes.do_not_populate
            properties["mounting_style"] = fp.attributes.mounting_style
            properties["mpn"] = ""
            for item in fp.texts_and_fields:
                if isinstance(item, Field) and len(item.text.value) and item.name == "MPN":
                    properties["mpn"] = item.text.value

        return properties

    def get_pins(self, footprint):
        """Get pins from a footprint"""
        pins = []

        if self.using_pcbnew:
            import pcbnew

            seen_numbers = set()

            for pad in footprint.Pads():
                if isinstance(pad, pcbnew.PAD):
                    number = pad.GetNumber()
                    if number in seen_numbers:
                        continue
                    else:
                        seen_numbers.add(number)

                    pins.append(
                        {
                            "number": number,
                            "pin_function": pad.GetPinFunction(),
                            "pin_type": pad.GetPinType(),
                            "netname": pad.GetNetname(),
                            "connected": ("no_connect" not in pad.GetPinType())
                            and pad.IsConnected(),
                            "position": (None, None),
                        }
                    )

        elif self.using_IPC:
            from kipy.board_types import FootprintInstance

            footprint_: FootprintInstance = footprint
            all_pads = footprint_.definition.pads
            for pad in all_pads:
                pins.append(
                    {
                        "number": pad.number,
                        # TODO: pin_function not yet available in IPC API
                        "pin_function": "pin_" + str(pad.number),
                        "pin_type": get_pad_type_name(pad.pad_type),
                        "netname": pad.net.name if pad.net else "",
                        "connected": bool(pad.net and pad.net.name),
                        "position": Vector2_to_mm(pad.position),
                    }
                )

        return pins
