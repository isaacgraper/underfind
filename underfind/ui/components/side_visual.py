import customtkinter as ctk
from PIL import Image, ImageTk
from underfind.ui.themes.tokens import Colors
import os

class SideVisual(ctk.CTkFrame):
    def __init__(self, master, theme: Colors = Colors.DARK, **kwargs):
        super().__init__(master, **kwargs)
        self.theme = theme
        self.configure(fg_color=self.theme["frame_color"])
        self._build_ui()

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    
        self.canvas = ctk.CTkCanvas(
            self,
            highlightthickness=0,
            bg=self.theme["frame_color"]
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self._load_image()
        
        self.bind("<Configure>", self._on_resize)
        
    def _load_image(self):
        """Carrega e exibe a imagem da capa lateral"""
        try:
            image_path = "underfind/ui/assets/login_visual.png"
            if os.path.exists(image_path):
                pil_image = Image.open(image_path)
                
                self.canvas.update_idletasks()
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                if canvas_width <= 1 or canvas_height <= 1:
                    canvas_width = 400
                    canvas_height = 600
                
                img_width, img_height = pil_image.size
                aspect_ratio = img_width / img_height
                canvas_aspect_ratio = canvas_width / canvas_height
                
                if aspect_ratio > canvas_aspect_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / aspect_ratio)
                else:
                    new_height = canvas_height
                    new_width = int(canvas_height * aspect_ratio)
                
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.image = ImageTk.PhotoImage(pil_image)
                
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                
                self.canvas.configure(width=canvas_width, height=canvas_height)
                self.canvas.create_image(x, y, image=self.image, anchor="nw")
            else:
                self._fallback_visual()
        except Exception as e:
            print(f"[WARN] Could not load image: {e}")
            self._fallback_visual()

    def _fallback_visual(self):
        """Fallback simples se não houver imagem"""
        self.canvas.configure(bg=self.theme["frame_color"])
        self.canvas.create_text(
            200, 300,
            fill=self.theme["accent"],
            font=("Segoe UI", 36, "bold")
        )
    
    def _on_resize(self, event):
        """Redimensiona a imagem quando o componente é redimensionado"""
        if hasattr(self, 'image'):
            self._load_image()
