import customtkinter as ctk
import threading
import time
from underfind.ui.themes.tokens import Colors

class Notification(ctk.CTkFrame):
    """Componente de notificação que sempre aparece centralizado no topo."""
    
    def __init__(self, master, message="", notification_type="info", duration=3000, theme: Colors = Colors.DARK, **kwargs):
        super().__init__(master, **kwargs)
        self.message = message
        self.notification_type = notification_type
        self.duration = duration
        self.is_visible = False
        self.theme = theme.value

        self.type_colors = {
            "success": {"bg": "#1B5E20", "border": "#4CAF50", "text": self.theme["text_color"]},
            "error": {"bg": "#B71C1C", "border": "#F44336", "text": self.theme["text_color"]},
            "warning": {"bg": "#E65100", "border": "#FF9800", "text": self.theme["text_color"]},
            "info": {"bg": self.theme["frame_color"], "border": self.theme["accent"], "text": self.theme["text_color"]}
        }

        self._build_notification()

    def _build_notification(self):
        colors = self.type_colors.get(self.notification_type, self.type_colors["info"])
        self.configure(
            fg_color=colors["bg"],
            border_width=1,
            border_color=colors["border"],
            corner_radius=12
        )

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=10)

        content_frame = ctk.CTkFrame(container, fg_color="transparent")
        content_frame.pack(fill="x")

        self.icon_label = ctk.CTkLabel(
            content_frame,
            text=self._get_icon(),
            font=("Segoe UI", 16),
            text_color=colors["text"]
        )
        self.icon_label.pack(side="left", padx=(0, 10))

        self.message_label = ctk.CTkLabel(
            content_frame,
            text=self.message,
            font=("Segoe UI", 14),
            text_color=colors["text"],
            wraplength=300
        )
        self.message_label.pack(side="left", fill="x", expand=True)

    def _get_icon(self):
        icons = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}
        return icons.get(self.notification_type, "ℹ")

    def show(self, message=None, notification_type=None, duration=None):
        if message:
            self.message = message
            self.message_label.configure(text=message)
        if notification_type:
            self.notification_type = notification_type
            colors = self.type_colors.get(notification_type, self.type_colors["info"])
            self.configure(fg_color=colors["bg"], border_color=colors["border"])
            self.icon_label.configure(text=self._get_icon(), text_color=colors["text"])
            self.message_label.configure(text_color=colors["text"])
        if duration:
            self.duration = duration

        self.is_visible = True

        # força layout e garante que apareça direto no topo centralizado
        self.master.update_idletasks()
        self.place(relx=0.5, rely=0.05, anchor="n")
        self.tkraise()

        if self.duration > 1000:
            threading.Thread(target=self._auto_hide, daemon=True).start()

    def hide(self):
        self.is_visible = False
        self.place_forget()

    def _auto_hide(self):
        time.sleep(self.duration / 1000)
        if self.is_visible:
            self.master.after(0, self.hide)


class NotificationManager:
    """Gerenciador de notificações: apenas uma visível por vez."""
    
    def __init__(self, master, theme: Colors = Colors.DARK):
        self.master = master
        self.theme = theme
        self.current_notification = None

    def show_notification(self, message, notification_type="info", duration=3000):
        if self.current_notification:
            self.current_notification.hide()
            self.current_notification.destroy()

        self.current_notification = Notification(
            self.master,
            message=message,
            notification_type=notification_type,
            duration=duration,
            theme=self.theme
        )
        self.current_notification.show()
        return self.current_notification

    # atalhos rápidos
    def success(self, message, duration=3000):
        return self.show_notification(message, "success", duration)

    def error(self, message, duration=5000):
        return self.show_notification(message, "error", duration)

    def warning(self, message, duration=4000):
        return self.show_notification(message, "warning", duration)

    def info(self, message, duration=3000):
        return self.show_notification(message, "info", duration)

    def clear_all(self):
        if self.current_notification:
            self.current_notification.hide()
            self.current_notification.destroy()
            self.current_notification = None
