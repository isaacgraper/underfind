import customtkinter as ctk
from tkinter import filedialog, messagebox
import csv
from typing import Optional, Callable, Dict, List, Any


# NOTE: KEYWORDS could be seeded externally if desired.
KEYWORDS: List[str] = []


class Filters(ctk.CTkFrame):
    """
    Filters panel with:
      - keyword text input + add button
      - CSV upload to import keywords
      - scrollable area listing keywords with checkboxes and remove buttons
      - numeric inputs for views and subscribers
      - numeric inputs for duration in seconds (and sliders synced to entries)
      - 'Aplicar Filtros' button which calls an optional callback with the filter dict

    Usage:
      f = Filters(parent, theme, on_apply=my_callback)
      my_callback(filters_dict)  # called when the user clicks 'Aplicar Filtros'
    """

    def __init__(self, master, theme: Dict[str, Any], on_apply: Optional[Callable[[Dict], None]] = None, **kwargs):
        # Ensure custom parameters (like on_apply) are not forwarded to CTkFrame,
        # since CTkFrame doesn't accept arbitrary kwargs and will raise.
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != "on_apply"}
        super().__init__(master, fg_color=theme.get("frame_color", "#1f1f1f"), width=280, **filtered_kwargs)
        self.theme = theme
        self.on_apply = on_apply

        # internal state
        self.keywords: List[str] = list(KEYWORDS)
        self.keyword_vars: Dict[str, ctk.BooleanVar] = {}

        # views/subs/duration vars
        self.min_views_var = ctk.StringVar(value="")
        self.max_views_var = ctk.StringVar(value="")
        self.max_subs_var = ctk.StringVar(value="")

        # duration as both entries and sliders (seconds)
        self.min_len_var = ctk.StringVar(value="0")
        self.max_len_var = ctk.StringVar(value="0")

        # build ui
        self.grid_propagate(False)
        self._build_ui()
        self._populate_keywords_ui()

    def _build_ui(self):
        # Title
        title = ctk.CTkLabel(self, text="Filtros", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(10, 6), anchor="w", padx=12)

        # Keywords input row
        kw_row = ctk.CTkFrame(self, fg_color="transparent")
        kw_row.pack(fill="x", padx=12, pady=(0, 8))
        self.keyword_entry = ctk.CTkEntry(kw_row, placeholder_text="Adicionar palavra-chave", height=32)
        self.keyword_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        add_btn = ctk.CTkButton(kw_row, text="Adicionar", width=90, command=self._on_add_keyword)
        add_btn.grid(row=0, column=1)
        kw_row.grid_columnconfigure(0, weight=1)

        # CSV upload button
        csv_row = ctk.CTkFrame(self, fg_color="transparent")
        csv_row.pack(fill="x", padx=12, pady=(0, 8))
        csv_btn = ctk.CTkButton(csv_row, text="Importar CSV", command=self._on_csv_upload)
        csv_btn.pack(side="left")
        csv_hint = ctk.CTkLabel(csv_row, text="(coluna 'keyword' ou primeira coluna)", text_color=self.theme.get("subtext_color"))
        csv_hint.pack(side="left", padx=(8, 0))

        # Scrollable area for keyword chips / checklist
        self.keywords_frame = ctk.CTkScrollableFrame(self, height=180, fg_color="transparent")
        self.keywords_frame.pack(fill="both", padx=12, pady=(4, 8))
        self.keywords_frame.grid_columnconfigure(0, weight=1)

        # Views inputs
        ctk.CTkLabel(self, text="Mínimo de Views:").pack(anchor="w", padx=12, pady=(6, 0))
        self.min_views = ctk.CTkEntry(self, textvariable=self.min_views_var, placeholder_text="Ex: 50000")
        self.min_views.pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkLabel(self, text="Máximo de Views:").pack(anchor="w", padx=12, pady=(6, 0))
        self.max_views = ctk.CTkEntry(self, textvariable=self.max_views_var, placeholder_text="Ex: 1000000 (ou vazio)")
        self.max_views.pack(fill="x", padx=12, pady=(0, 6))

        # Subscribers
        ctk.CTkLabel(self, text="Máx. Inscritos:").pack(anchor="w", padx=12, pady=(6, 0))
        self.max_subs = ctk.CTkEntry(self, textvariable=self.max_subs_var, placeholder_text="Ex: 20000")
        self.max_subs.pack(fill="x", padx=12, pady=(0, 6))

        # Duration controls: numeric entries for seconds + sliders synced
        ctk.CTkLabel(self, text="Duração (segundos) - mínimo:").pack(anchor="w", padx=12, pady=(8, 0))
        duration_min_row = ctk.CTkFrame(self, fg_color="transparent")
        duration_min_row.pack(fill="x", padx=12)
        self.min_len_entry = ctk.CTkEntry(duration_min_row, textvariable=self.min_len_var, width=80)
        self.min_len_entry.grid(row=0, column=0, sticky="w")
        self.min_len_slider = ctk.CTkSlider(duration_min_row, from_=0, to=7200, number_of_steps=720, command=self._on_min_len_slider)
        self.min_len_slider.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        duration_min_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Duração (segundos) - máximo:").pack(anchor="w", padx=12, pady=(8, 0))
        duration_max_row = ctk.CTkFrame(self, fg_color="transparent")
        duration_max_row.pack(fill="x", padx=12)
        self.max_len_entry = ctk.CTkEntry(duration_max_row, textvariable=self.max_len_var, width=80)
        self.max_len_entry.grid(row=0, column=0, sticky="w")
        self.max_len_slider = ctk.CTkSlider(duration_max_row, from_=0, to=7200, number_of_steps=720, command=self._on_max_len_slider)
        self.max_len_slider.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        duration_max_row.grid_columnconfigure(1, weight=1)

        # Bind entries to validate / sync on focus out
        self.min_len_entry.bind("<FocusOut>", lambda e: self._on_min_len_entry())
        self.max_len_entry.bind("<FocusOut>", lambda e: self._on_max_len_entry())

        # Apply button
        apply_btn = ctk.CTkButton(self, text="Aplicar Filtros", command=self._apply_filters)
        apply_btn.pack(fill="x", padx=12, pady=(12, 12))

    # -------------------------
    # Keyword management
    # -------------------------
    def _on_add_keyword(self):
        val = (self.keyword_entry.get() or "").strip()
        if not val:
            return
        # support comma-separated input to add many at once
        parts = [p.strip() for p in val.split(",") if p.strip()]
        added = 0
        for p in parts:
            if p not in self.keywords:
                self.keywords.append(p)
                added += 1
        if added > 0:
            self._populate_keywords_ui()
        self.keyword_entry.delete(0, "end")

    def _on_csv_upload(self):
        path = filedialog.askopenfilename(title="Selecionar CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        keys_added = 0
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                candidate = None
                if reader.fieldnames:
                    # try to find a keyword-like column
                    for name in ("keyword", "keywords", "query", "q"):
                        if name in reader.fieldnames:
                            candidate = name
                            break
                    if not candidate:
                        # fallback: use first column
                        candidate = reader.fieldnames[0]

                # If CSV had headers, use DictReader; otherwise, fallback to simple reader
                if candidate:
                    for row in reader:
                        keyword = (row.get(candidate) or "").strip()
                        if keyword and keyword not in self.keywords:
                            self.keywords.append(keyword)
                            keys_added += 1
                else:
                    # CSV without headers - read first column of each row
                    fh.seek(0)
                    simple_reader = csv.reader(fh)
                    for row in simple_reader:
                        if not row:
                            continue
                        keyword = (row[0] or "").strip()
                        if keyword and keyword not in self.keywords:
                            self.keywords.append(keyword)
                            keys_added += 1
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao ler o CSV: {e}")
            return

        if keys_added > 0:
            self._populate_keywords_ui()
        messagebox.showinfo("Importação CSV", f"{keys_added} palavra(s)-chave importada(s).")

    def _populate_keywords_ui(self):
        """
        Rebuild the keywords_frame contents to reflect current self.keywords.
        Each keyword will have a checkbox (to include) and a remove button.
        """
        # clear existing children
        for child in list(self.keywords_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        self.keyword_vars.clear()

        if not self.keywords:
            lbl = ctk.CTkLabel(self.keywords_frame, text="Nenhuma palavra-chave adicionada.", text_color=self.theme.get("subtext_color"))
            lbl.pack(padx=6, pady=8)
            return

        for idx, kw in enumerate(self.keywords):
            row = ctk.CTkFrame(self.keywords_frame, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            row.grid_columnconfigure(0, weight=1)

            var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(row, text=kw, variable=var, onvalue=True, offvalue=False)
            chk.grid(row=0, column=0, sticky="w", padx=(6, 4))
            # remove button
            rm_btn = ctk.CTkButton(row, text="Remover", width=80, command=lambda k=kw: self._remove_keyword(k))
            rm_btn.grid(row=0, column=1, padx=(4, 6))

            self.keyword_vars[kw] = var

    def _remove_keyword(self, keyword: str):
        try:
            if keyword in self.keywords:
                self.keywords.remove(keyword)
            if keyword in self.keyword_vars:
                del self.keyword_vars[keyword]
            self._populate_keywords_ui()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível remover a palavra-chave: {e}")

    # -------------------------
    # Duration slider / entry sync
    # -------------------------
    def _on_min_len_slider(self, value):
        # slider passes float values; ensure integer seconds
        try:
            ival = int(float(value))
            if ival < 0:
                ival = 0
            self.min_len_var.set(str(ival))
        except Exception:
            # ignore invalid slider input
            pass

    def _on_max_len_slider(self, value):
        try:
            ival = int(float(value))
            if ival < 0:
                ival = 0
            self.max_len_var.set(str(ival))
        except Exception:
            pass

    def _on_min_len_entry(self):
        val = (self.min_len_var.get() or "").strip()
        try:
            ival = int(val)
            if ival < 0:
                ival = 0
        except Exception:
            ival = 0
        # clamp to slider range
        if ival > 7200:
            ival = 7200
        self.min_len_var.set(str(ival))
        try:
            self.min_len_slider.set(ival)
        except Exception:
            pass

    def _on_max_len_entry(self):
        val = (self.max_len_var.get() or "").strip()
        try:
            ival = int(val)
            if ival < 0:
                ival = 0
        except Exception:
            ival = 0
        if ival > 7200:
            ival = 7200
        self.max_len_var.set(str(ival))
        try:
            self.max_len_slider.set(ival)
        except Exception:
            pass

    # -------------------------
    # Apply filters
    # -------------------------
    def _apply_filters(self):
        """
        Collect current filter values and call the on_apply callback (if any)
        The returned dict uses keys expected by Dashboard._on_filters_apply:
          - keywords: List[str]
          - min_views, max_views
          - max_subscribers
          - duration_seconds_min, duration_seconds_max
        """
        # Keywords: those checked; if none checked but keywords exist, return all keywords
        selected = [k for k, v in self.keyword_vars.items() if v.get()]
        if not selected and self.keywords:
            selected = list(self.keywords)

        def to_int_or_none(s: str) -> Optional[int]:
            try:
                s = (s or "").strip()
                if s == "":
                    return None
                return int(s)
            except Exception:
                return None

        filters = {
            "keywords": selected,
            "min_views": to_int_or_none(self.min_views_var.get()),
            "max_views": to_int_or_none(self.max_views_var.get()),
            # keep naming compatibility: Dashboard expects 'max_subscribers' in its docstring, but controller uses max_views/max_subs mapping.
            "max_subscribers": to_int_or_none(self.max_subs_var.get()),
            "duration_seconds_min": to_int_or_none(self.min_len_var.get()),
            "duration_seconds_max": to_int_or_none(self.max_len_var.get()),
        }

        # notify via callback
        try:
            if callable(self.on_apply):
                self.on_apply(filters)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao aplicar filtros: {e}")
