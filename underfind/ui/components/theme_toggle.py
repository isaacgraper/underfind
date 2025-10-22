import customtkinter as ctk
from underfind.ui.frames.auth import AuthFrame
from underfind.ui.components.notification import NotificationManager
from underfind.ui.themes.tokens import Colors
import threading
import time

class ThemeToggleButton(ctk.CTkButton):
    """Componente independente do botão de alternar tema"""
    def __init__(self, master, command, palette, **kwargs):
        super().__init__(
            master,
            text="Alternar Tema",
            fg_color=palette["accent"],
            hover_color=palette["hover"],
            text_color="white",
            command=command,
            **kwargs
        )
        self.place(x=20, y=20)

    def update_palette(self, palette):
        """Atualiza cores do botão quando o tema muda"""
        self.configure(fg_color=palette["accent"], hover_color=palette["hover"])

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UnderFind")
        self.geometry("1200x700")
        self.resizable(False, False)

        self.current_theme = Colors.DARK
        self.palette = Colors.apply(self, self.current_theme)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.notification_manager = NotificationManager(self)

        # Tela de loading inicial
        self.loading_frame = ctk.CTkFrame(self, fg_color=self.palette["surface"])
        self.loading_label = ctk.CTkLabel(self.loading_frame, text="Loading...", font=("Segoe UI", 24))
        self.loading_label.pack(expand=True)
        self.loading_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Botão de tema como componente
        self.toggle_btn = ThemeToggleButton(self, command=self._toggle_theme, palette=self.palette)

        # Carrega AuthFrame com efeito de loading
        self.after(500, self._load_auth_with_loading)

    def _load_auth_with_loading(self):
        self.loading_frame.lift()
        self.loading_frame.update()
        threading.Thread(target=self._simulate_load, daemon=True).start()

    def _simulate_load(self):
        time.sleep(0.5)
        self.after(0, self._load_auth)

    def _load_auth(self):
        if hasattr(self, "current_frame"):
            self.current_frame.destroy()

        self.current_frame = AuthFrame(
            self,
            theme=self.current_theme,
            notification_manager=self.notification_manager
        )
        self.current_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.loading_frame.lower()  # remove loading

    def _toggle_theme(self):
        self.current_theme = Colors.LIGHT if self.current_theme == Colors.DARK else Colors.DARK
        self.palette = Colors.apply(self, self.current_theme)

        self.configure(fg_color=self.palette["fg_color"])

        # Atualiza botão via componente
        self.toggle_btn.update_palette(self.palette)

        # Mostra loading enquanto troca tema
        self.loading_frame.lift()
        self.loading_frame.update()
        threading.Thread(target=self._simulate_load, daemon=True).start()
