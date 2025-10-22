import customtkinter as ctk
from underfind.ui.themes.tokens import Colors
from underfind.ui.components.sidebar import Sidebar
from underfind.ui.components.topbar import Topbar

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, theme: Colors = Colors.DARK, notification_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.theme = theme.value
        self.notification_manager = notification_manager
        self.configure(fg_color=self.theme["fg_color"])
        self._build_ui()

    def _build_ui(self):
        # Grid principal
        self.grid_columnconfigure(0, weight=0)  # Sidebar
        self.grid_columnconfigure(1, weight=1)  # Área principal
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(self, self.theme)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Área principal
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)

        # Top bar
        self.top_bar = Topbar(self.main_area, self.theme)
        self.top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))