import customtkinter as ctk
from underfind.ui.components.input import CustomInput
from underfind.ui.components.button import CustomButton
from underfind.ui.components.side_visual import SideVisual
from underfind.ui.components.social_login import TermsCheckbox
from underfind.controllers.auth import AuthController
from underfind.ui.themes.tokens import Colors
from underfind.ui.components.notification import NotificationManager

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AuthFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        theme: Colors = Colors.DARK,
        notification_manager=None,
        on_login_success=None,
        on_register=None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.theme = theme.value
        self.controller = AuthController()
        self.mode = "login"
        self.on_login_success = on_login_success
        self.on_register = on_register

        self.notification: NotificationManager = notification_manager

        self.configure(fg_color=self.theme["fg_color"])
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self.visual = SideVisual(self, theme=self.theme)
        self.visual.grid(row=0, column=0, sticky="nsew", padx=(10, 5))

        self.form_container = ctk.CTkFrame(self, fg_color="transparent")
        self.form_container.grid(row=0, column=1, sticky="nsew", padx=(5, 10))
        self.form_container.grid_columnconfigure(0, weight=1)
        self.form_container.grid_rowconfigure(0, weight=1)

        self.form_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        self.form_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self._build_form()

    def _clear_form(self):
        for widget in self.form_frame.winfo_children():
            widget.destroy()

    def _build_form(self):
        self._clear_form()

        title_text = "Create an account" if self.mode == "register" else "Welcome back"
        subtitle_text = "Already have an account?" if self.mode == "register" else "Don't have an account?"
        switch_text = "Log in" if self.mode == "register" else "Sign up"

        ctk.CTkLabel(
            self.form_frame,
            text=title_text,
            font=("Segoe UI", 28, "bold"),
            text_color=self.theme["text_color"]
        ).pack(pady=(40, 10))

        prompt_frame = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        prompt_frame.pack(pady=(0, 40))
        ctk.CTkLabel(
            prompt_frame,
            text=subtitle_text,
            font=("Segoe UI", 14),
            text_color=self.theme["text_color"]
        ).pack(side="left")
        
        ctk.CTkButton(
            prompt_frame,
            text=switch_text,
            fg_color="transparent",
            text_color=self.theme["accent"],
            hover_color=self.theme["text_color"],
            font=("Segoe UI", 14, "bold"),
            command=self._toggle_mode,
            width=0
        ).pack(side="left", padx=(5, 0))

        if self.mode == "register":
            self._build_name_fields()

        self.email = CustomInput(self.form_frame, placeholder="Email", theme=self.theme)
        self.email.pack(fill="x", pady=(0, 15))
        self.password = CustomInput(self.form_frame, placeholder="Enter your password", show="*", theme=self.theme)
        self.password.pack(fill="x", pady=(0, 15))

        if self.mode == "register":
            self.confirm_password = CustomInput(self.form_frame, placeholder="Confirm password", show="*", theme=self.theme)
            self.confirm_password.pack(fill="x", pady=(0, 15))
            self.terms_checkbox = TermsCheckbox(self.form_frame, theme=self.theme)
            self.terms_checkbox.pack(pady=(0, 30))

        main_btn_text = "Create account" if self.mode == "register" else "Sign in"
        self.main_button = CustomButton(self.form_frame, text=main_btn_text, command=self._on_main_click, theme=self.theme)
        self.main_button.pack(fill="x", pady=(0, 30))

    def _build_name_fields(self):
        name_frame = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        name_frame.pack(fill="x", pady=(0, 15))
        name_frame.grid_columnconfigure(0, weight=1)
        name_frame.grid_columnconfigure(1, weight=1)

        self.first_name = CustomInput(name_frame, placeholder="First name", theme=self.theme)
        self.first_name.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.last_name = CustomInput(name_frame, placeholder="Last name", theme=self.theme)
        self.last_name.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self._build_form()

    def _on_main_click(self):
        email = self.email.get()
        password = self.password.get()

        if self.mode == "login":
            user = self.controller.login(email, password)
            if user:
                self.notification.success("Login realizado com sucesso!")
                if self.on_login_success:
                    self.on_login_success()
            else:
                self.notification.error("Email ou senha incorretos.")
        else:
            if hasattr(self, "terms_checkbox") and not self.terms_checkbox.get():
                self.notification.warning("Por favor aceite os termos de uso.")
                return

            confirm = self.confirm_password.get()
            user = self.controller.register(email, password, confirm)
            if user:
                self.notification.success("Registro realizado com sucesso!")
                if self.on_register:
                    self.on_register()
                self._toggle_mode()
            else:
                self.notification.error("Falha no registro.")


