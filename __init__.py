import pcbnew

from .KiCadPinout import plugin_action
from .KiCadPinout.kicad_manager import KiCadBoardManager


class ActionKiCadPlugin(pcbnew.ActionPlugin):  # type: ignore[misc]
    def defaults(self) -> None:
        from pathlib import Path

        self.name = "Pinout Generator (pcbnew)"
        self.category = "Read PCB"
        self.description = "Generates pinout exports from the PCB nets"
        self.show_toolbar_button = True
        icon_path = Path(__file__).parent / "KiCadPinout" / "icon.png"
        self.icon_file_name = str(icon_path)
        self.dark_icon_file_name = str(icon_path)

    def Run(self) -> None:
        plugin_action.KiCadPinout(KiCadBoardManager()).ShowModal()


ActionKiCadPlugin().register()
