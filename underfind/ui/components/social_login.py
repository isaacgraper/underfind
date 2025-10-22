import customtkinter as ctk
from underfind.ui.themes.tokens import Colors

class TermsCheckbox(ctk.CTkCheckBox):
    def __init__(self, master, theme: Colors = Colors.DARK, **kwargs):
        self.theme = theme

        super().__init__(
            master,
            text="I agree to the Terms & Conditions",
            height=20,
            corner_radius=4,
            border_width=1,
            fg_color=self.theme["accent"],           # vermelho YouTube
            hover_color=self.theme["hover"],         # vermelho mais escuro
            border_color=self.theme["accent"],
            checkmark_color=self.theme["text_color"],
            text_color=self.theme["text_color"],
            text_color_disabled=self.theme["subtext_color"],
            font=("Segoe UI", 12),
            **kwargs
        )
