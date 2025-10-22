import customtkinter as ctk

class LoadingOverlay:
    def __init__(self, master):
        self.master = master
        self.overlay_frame = None
        self.label = None
        self.alpha = 0.0

    def show(self, text="Carregando..."):
        """Mostra a tela de loading"""
        if self.overlay_frame:
            return

        # Cria frame overlay
        self.overlay_frame = ctk.CTkFrame(
            self.master,
            fg_color="black",
            corner_radius=0
        )
        
        # Posiciona o overlay cobrindo toda a janela
        self.overlay_frame.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Texto central
        self.label = ctk.CTkLabel(
            self.overlay_frame,
            text=text,
            font=("Segoe UI", 18, "bold"),
            text_color="white",
            fg_color="transparent"
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")

        # Fade in
        self.alpha = 0.0
        self._fade_in()

    def _fade_in(self):
        """Animação suave de entrada."""
        if self.alpha < 0.8:
            self.alpha += 0.05
            # Simula transparência mudando a cor
            gray_value = int(255 * (1 - self.alpha))
            color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"
            self.overlay_frame.configure(fg_color=color)
            self.master.after(30, self._fade_in)
        else:
            self.overlay_frame.configure(fg_color="#333333")

    def _fade_out(self):
        """Animação suave de saída."""
        if self.alpha > 0:
            self.alpha -= 0.05
            gray_value = int(255 * (1 - self.alpha))
            color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"
            self.overlay_frame.configure(fg_color=color)
            self.master.after(30, self._fade_out)
        else:
            self.hide(destroy=True)

    def hide(self, destroy=False):
        """Esconde o overlay de loading"""
        if not self.overlay_frame:
            return
            
        try:
            if destroy:
                self.overlay_frame.destroy()
                self.overlay_frame = None
                self.label = None
                self.alpha = 0.0
            else:
                self._fade_out()
        except Exception as e:
            print(f"[DEBUG] Error hiding overlay: {e}")
            # Força destruição em caso de erro
            try:
                if self.overlay_frame:
                    self.overlay_frame.destroy()
            except:
                pass
            self.overlay_frame = None
            self.label = None
            self.alpha = 0.0

    def update_text(self, text):
        """Atualiza o texto do loading"""
        if self.overlay_frame and self.label:
            self.label.configure(text=text)

