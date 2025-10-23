import customtkinter as ctk

class Topbar(ctk.CTkFrame):
    def __init__(self, master, theme: dict, title="Dashboard", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.theme = theme
        self.title = title
        self.grid_columnconfigure(1, weight=1)
        self._build_ui()

    def _build_ui(self):
        # Busca
        search_frame = ctk.CTkFrame(self, fg_color=self.theme["entry_color"])
        search_frame.grid(row=0, column=1, sticky="ew", padx=(20, 0))
        ctk.CTkEntry(
            search_frame,
            placeholder_text="Pesquise o seu próximo nicho...",
            height=35,
            corner_radius=8,
            border_width=1,
            fg_color=self.theme["entry_color"],
            border_color=self.theme["border_color"],
            text_color=self.theme["text_color"],
            placeholder_text_color=self.theme["subtext_color"],
            font=("Segoe UI", 14)
        ).pack(fill="x", padx=10, pady=10)
