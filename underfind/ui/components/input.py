import customtkinter as ctk
from underfind.ui.themes.tokens import Colors

class CustomInput(ctk.CTkEntry):
    def __init__(self, master, placeholder="", theme: Colors = Colors.DARK, **kwargs):
        self.palette = theme
        
        super().__init__(
            master,
            placeholder_text=placeholder,
            height=40,
            corner_radius=8,
            border_width=1,
            fg_color=self.palette["entry_color"],
            border_color=self.palette["border_color"],
            text_color=self.palette["text_color"],
            placeholder_text_color=self.palette["subtext_color"],
            font=("Segoe UI", 14),
            **kwargs
        )
        
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
    
    def _on_focus_in(self, event):
        self.configure(border_color=self.palette["accent"])
    
    def _on_focus_out(self, event):
        self.configure(border_color=self.palette["border_color"])

    def update_theme(self, theme: Colors):
        self.palette = theme.value
        self.configure(
            fg_color=self.palette["entry_color"],
            border_color=self.palette["border_color"],
            text_color=self.palette["text_color"],
            placeholder_text_color=self.palette["subtext_color"],
        )
