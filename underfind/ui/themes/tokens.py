from enum import Enum
import customtkinter as ctk
from dataclasses import dataclass

class Colors(Enum):
    LIGHT = {
        "fg_color": "#FFFFFF",
        "frame_color": "#F9F9F9",
        "text_color": "#0F0F0F",
        "subtext_color": "#606060",
        "accent": "#FF0000",
        "hover": "#E53935",
        "button_color": "#F2F2F2",
        "entry_color": "#FFFFFF",
        "border_color": "#E0E0E0"
    }

    DARK = {
        "fg_color": "#0F0F0F",
        "frame_color": "#181818",
        "text_color": "#FFFFFF",
        "subtext_color": "#AAAAAA",
        "accent": "#FF0000",
        "hover": "#E53935",
        "button_color": "#272727",
        "entry_color": "#121212",
        "border_color": "#303030"
    }

    @staticmethod
    def apply(app: ctk.CTk, mode: "Colors"):
        palette = mode.value
        ctk.set_appearance_mode("dark" if mode == Colors.DARK else "light")
        app.configure(fg_color=palette["fg_color"])
        return palette

class Status(Enum):
    SUCCESS = {
        "bg": "#1B5E20",
        "border": "#4CAF50",
        "text": "#FFFFFF"
    }
    ERROR = {
        "bg": "#B71C1C",
        "border": "#F44336",
        "text": "#FFFFFF"
    }
    WARNING = {
        "bg": "#E65100",
        "border": "#FF9800",
        "text": "#FFFFFF"
    }
    INFO = {
        "bg": "#151425",
        "border": "#7B61FF",
        "text": "#FFFFFF"
    }

@dataclass(frozen=True)
class Sizes:
    radius: int = 12
    control_height: int = 40
    padding_x: int = 80
    padding_y: int = 10