import customtkinter as ctk
from underfind.ui.themes.tokens import Colors

class CustomButton(ctk.CTkButton):
    def __init__(self, master, text="", theme: Colors = Colors.DARK, **kwargs):
        self.palette = theme

        super().__init__(
            master,
            text=text,
            height=40,
            corner_radius=8,
            fg_color=self.palette["entry_color"],
            hover_color=self.palette["border_color"],
            text_color=self.palette["text_color"],
            font=("Segoe UI", 14, "bold"),
            **kwargs
        )
