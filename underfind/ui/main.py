import customtkinter as ctk
from underfind.ui.frames.auth import AuthFrame
from underfind.ui.frames.dashboard import DashboardFrame
from underfind.ui.components.notification import NotificationManager
from underfind.ui.components.loading import LoadingOverlay
from underfind.ui.themes.tokens import Colors


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("underfind")
        
        self._setup_window()

        self.current_theme = Colors.DARK
        self.palette = Colors.apply(self, self.current_theme)

        self.notification_manager = NotificationManager(master=self)

        self.frames = {}
        self.show_frame("AuthFrame")

    def _setup_window(self):
        """
        Configura a janela principal de forma responsiva
        """
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        if screen_width >= 1920:  # Full HD
            window_width = 1200
            window_height = 800
        elif screen_width >= 1366:  # HD
            window_width = 1024
            window_height = 768
        else:
            window_width = min(900, screen_width - 100)
            window_height = min(700, screen_height - 100)
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(800, 600)
        self.resizable(True, True)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def show_frame(self, frame_name):
        """
        Exibe o frame desejado, criando se necessário
        """

        if frame_name not in self.frames:
            if frame_name == "AuthFrame":
                self.frames[frame_name] = AuthFrame(
                    master=self,
                    notification_manager=self.notification_manager,
                    on_login_success = lambda: self.show_frame("DashboardFrame")
                )
            elif frame_name == "DashboardFrame":
                self.frames[frame_name] = DashboardFrame(self)
            else:
                raise ValueError(f"Frame {frame_name} is not defined")

            self.frames[frame_name].grid(row=0, column=0, sticky="nsew")

        self.frames[frame_name].tkraise()