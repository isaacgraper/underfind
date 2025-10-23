import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, theme: dict, **kwargs):
        super().__init__(master, fg_color=theme["frame_color"], width=250, **kwargs)
        self.theme = theme
        self.grid_propagate(False)
        self._build_ui()

    def _build_ui(self):
        # Logo
        ctk.CTkLabel(
            self,
            text="underfind",
            font=("Segoe UI", 24, "bold"),
            text_color=self.theme["accent"]
        ).pack(pady=(20, 30))

        # Navegação
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=20)
        nav_items = [("Dashboard", "dashboard"), ("Profile", "profile"), ("Settings", "settings")]
        for text, icon in nav_items:
            ctk.CTkButton(
                nav_frame,
                text=text,
                height=40,
                corner_radius=8,
                fg_color="transparent",
                hover_color=self.theme["border_color"],
                text_color=self.theme["text_color"],
                font=("Segoe UI", 14),
                anchor="w"
            ).pack(fill="x", pady=5)
