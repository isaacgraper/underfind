import logging
import threading
import io
import os
from typing import List, Optional, Iterable, Dict, Any

import customtkinter as ctk
from PIL import Image, ImageTk

from underfind.ui.themes.tokens import Colors
from underfind.ui.components.sidebar import Sidebar
from underfind.ui.components.filters import Filters
from underfind.ui.components.loading import LoadingOverlay
from underfind.models.video import Video
from underfind.controllers.search import SearchController

logger = logging.getLogger(__name__)


class DashboardFrame(ctk.CTkFrame):
    """
    DashboardFrame (modernized + connected):

    - Left: Sidebar
    - Center: Topbar + Search + Results area
    - Right: Filters (connected to dashboard via callback)

    Features implemented here:
    - Filters.on_apply is wired to trigger a search
    - Top search entry triggers search on Enter
    - Search performed by SearchController in a background thread
    - Loading overlay displayed during network operations
    - Results rendered as cards with thumbnail, title, stats and channel name
    - Thumbnail bytes are used to create ImageTk.PhotoImage (kept in memory to avoid GC)
    """

    SIDEBAR_DEFAULT_WIDTH = 250
    FILTERS_DEFAULT_WIDTH = 280

    def __init__(self, master, theme: Colors = Colors.DARK, notification_manager=None, **kwargs):
        super().__init__(master, **kwargs)

        # theme: accept Colors enum or raw dict
        if hasattr(theme, "value"):
            self.theme = theme.value
        else:
            self.theme = theme or {}

        self.notification_manager = notification_manager
        self.configure(fg_color=self.theme.get("fg_color", "transparent"))

        # UI state
        self._sidebar_visible = True
        self._filters_visible = True
        self._image_refs: Dict[str, ImageTk.PhotoImage] = {}  # keep refs to images to prevent GC

        # search controller (will read API key from env if not provided)
        self.search_controller = SearchController(
            api_key=os.environ.get("YOUTUBE_API_KEY"),
            loading_overlay=None,  # we use our own overlay in the frame
        )

        # create a loading overlay instance bound to the whole dashboard
        self.loading = LoadingOverlay(self)

        # build layout
        self._build_ui()

        # responsive binding
        self.bind("<Configure>", self._on_resize)

    def _build_ui(self):
        # layout columns: sidebar (fixed) | main (expand) | filters (fixed)
        self.grid_columnconfigure(0, weight=0, minsize=self.SIDEBAR_DEFAULT_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=self.FILTERS_DEFAULT_WIDTH)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(self, self.theme)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)

        # Filters (right) - pass callback to receive applied filters
        self.filters = Filters(self, self.theme, on_apply=self._on_filters_apply)
        self.filters.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)

        # Main area (center)
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=10)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)

        # Topbar
        self._build_topbar()

        # Results area
        self._build_results_area()

    def _build_topbar(self):
        topbar = ctk.CTkFrame(self.main_area, fg_color=self.theme.get("frame_color"), height=64, corner_radius=12)
        topbar.grid(row=0, column=0, sticky="ew", padx=(0, 0), pady=(0, 12))
        topbar.grid_columnconfigure(0, weight=0)
        topbar.grid_columnconfigure(1, weight=1)
        topbar.grid_columnconfigure(2, weight=0)

        # Sidebar toggle
        self._sb_toggle_btn = ctk.CTkButton(
            topbar,
            text="☰",
            width=42,
            height=42,
            fg_color="transparent",
            hover_color=self.theme.get("border_color"),
            text_color=self.theme.get("text_color"),
            command=self.toggle_sidebar,
            corner_radius=10,
        )
        self._sb_toggle_btn.grid(row=0, column=0, padx=(12, 6), pady=10)

        # Search entry
        self.search_entry = ctk.CTkEntry(
            topbar,
            placeholder_text="Pesquise o seu próximo nicho...",
            height=40,
            corner_radius=10,
            border_width=1,
            fg_color=self.theme.get("entry_color"),
            border_color=self.theme.get("border_color"),
            text_color=self.theme.get("text_color"),
            placeholder_text_color=self.theme.get("subtext_color"),
            font=("Segoe UI", 14),
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=10)
        self.search_entry.bind("<Return>", self._on_search_submit)

        # Suggestions box (simple)
        self.suggestion_box = ctk.CTkTextbox(
            topbar,
            width=200,
            height=100,
            fg_color=self.theme.get("frame_color"),
            corner_radius=8,
            state="disabled",
            wrap="word",
            border_width=0,
        )
        self.suggestion_box.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(0, 6))
        self.suggestion_box.grid_remove()
        self.search_entry.bind("<KeyRelease>", self._on_search_typing)

        # Filters toggle
        self._filters_toggle_btn = ctk.CTkButton(
            topbar,
            text="⚙",
            width=42,
            height=42,
            fg_color="transparent",
            hover_color=self.theme.get("border_color"),
            text_color=self.theme.get("text_color"),
            command=self.toggle_filters,
            corner_radius=10,
        )
        self._filters_toggle_btn.grid(row=0, column=2, padx=(6, 12), pady=10)

    def _build_results_area(self):
        container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.results_scroll = ctk.CTkScrollableFrame(container, fg_color=self.theme.get("card_bg", "transparent"))
        self.results_scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.results_scroll.grid_columnconfigure(0, weight=1)

        self.no_results_label = ctk.CTkLabel(self.results_scroll, text="Nenhum resultado. Faça uma busca!", font=("Segoe UI", 14))
        # initially hidden
        self.no_results_label.pack_forget()

    # ---------------------------
    # Interaction Handlers
    # ---------------------------

    def toggle_sidebar(self):
        if self._sidebar_visible:
            self.sidebar.grid_remove()
            self.grid_columnconfigure(0, weight=0, minsize=0)
            self._sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
            self.grid_columnconfigure(0, weight=0, minsize=self.SIDEBAR_DEFAULT_WIDTH)
            self._sidebar_visible = True

    def toggle_filters(self):
        if self._filters_visible:
            self.filters.grid_remove()
            self.grid_columnconfigure(2, weight=0, minsize=0)
            self._filters_visible = False
        else:
            self.filters.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)
            self.grid_columnconfigure(2, weight=0, minsize=self.FILTERS_DEFAULT_WIDTH)
            self._filters_visible = True

    def _on_resize(self, event):
        try:
            width = event.width
        except Exception:
            width = self.winfo_width()

        # hide filters on small widths
        if width < 900 and self._filters_visible:
            self.filters.grid_remove()
            self.grid_columnconfigure(2, weight=0, minsize=0)
            self._filters_visible = False
        elif width >= 900 and not self._filters_visible:
            self.filters.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)
            self.grid_columnconfigure(2, weight=0, minsize=self.FILTERS_DEFAULT_WIDTH)
            self._filters_visible = True

    # ---------------------------
    # Search & Filters integration
    # ---------------------------

    def _on_search_typing(self, event):
        q = self.search_entry.get().strip()
        if not q:
            self.suggestion_box.grid_remove()
            return
        # simple suggestions
        suggestions = [q, f"{q} tips", f"{q} trends", f"{q} 2025"]
        self._show_suggestions(suggestions)

    def _show_suggestions(self, suggestions: List[str]):
        try:
            self.suggestion_box.configure(state="normal")
            self.suggestion_box.delete("1.0", "end")
            for s in suggestions:
                self.suggestion_box.insert("end", f"• {s}\n")
            self.suggestion_box.configure(state="disabled")
            self.suggestion_box.grid()
        except Exception:
            # ignore UI errors
            pass

    def _on_search_submit(self, event=None):
        query = self.search_entry.get().strip()
        if not query:
            return
        # Run search with single keyword
        self._run_search(keywords=[query], filters=None)

    def _on_filters_apply(self, filters: Dict[str, Any]):
        """
        Called when Filters.on_apply is used.
        `filters` will contain keys including:
         - keywords: List[str]
         - min_views, max_views, max_subscribers
         - duration_seconds_min, duration_seconds_max
        """
        keywords = filters.get("keywords") or []
        # If no keywords provided, use the search entry text as a single query
        if not keywords:
            entry_val = self.search_entry.get().strip()
            if entry_val:
                keywords = [entry_val]
        # Map filter keys to controller's expected keys
        mapped = {
            "min_views": filters.get("min_views"),
            "max_views": filters.get("max_views"),
            "duration_seconds_min": filters.get("duration_seconds_min"),
            "duration_seconds_max": filters.get("duration_seconds_max"),
        }
        self._run_search(keywords=keywords, filters=mapped)

    def _run_search(self, keywords: Iterable[str], filters: Optional[Dict[str, Any]] = None):
        """
        Spawn background thread to run the search using SearchController.
        Shows loading overlay while running.
        """
        kw_list = [k for k in (keywords or []) if k and str(k).strip()]
        if not kw_list:
            # show message to user
            self._show_no_results("Insira palavras-chave para pesquisar.")
            return

        # show loading
        try:
            self.loading.show("Buscando vídeos...")
        except Exception:
            pass

        def worker():
            try:
                # perform search; request thumbnails to be fetched (controller may fetch or we will handle)
                videos: List[Video] = self.search_controller.search(keywords=kw_list, filters=filters, fetch_thumbnails=True)
                # Ensure thumbnails: if bytes not present, attempt to download a small version (best-effort)
                for v in videos:
                    if not getattr(v, "_thumbnail_bytes", None) and v.thumbnail_url:
                        try:
                            import requests

                            resp = requests.get(v.thumbnail_url, timeout=6)
                            if resp.ok:
                                v._thumbnail_bytes = resp.content
                        except Exception:
                            v._thumbnail_bytes = None
                # schedule render on main thread
                self.after(0, lambda: self._render_videos(videos))
            except Exception as e:
                logger.exception("Search failed: %s", e)
                msg = f"Erro durante a busca: {e}"
                self.after(0, lambda m=msg: self._show_no_results(m))
            finally:
                # hide loading overlay on main thread
                try:
                    self.after(0, lambda: self.loading.hide(destroy=True))
                except Exception:
                    pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ---------------------------
    # Rendering results
    # ---------------------------
    def _clear_results(self):
        # remove children frames inside results_scroll
        for child in self.results_scroll.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._image_refs.clear()

    def _show_no_results(self, message: str = "Nenhum resultado. Faça uma busca!"):
        self._clear_results()
        lbl = ctk.CTkLabel(self.results_scroll, text=message, font=("Segoe UI", 14))
        lbl.pack(pady=20)

    def _render_videos(self, videos: List[Video]):
        """
        Render a list of Video models into the scrollable results area.
        Creates card-like frames with thumbnail (if available), title, stats and channel.
        """
        self._clear_results()
        if not videos:
            self._show_no_results()
            return

        for idx, video in enumerate(videos):
            try:
                card = ctk.CTkFrame(self.results_scroll, fg_color=self.theme.get("frame_color"), corner_radius=12)
                card.pack(fill="x", padx=8, pady=8)
                card.grid_columnconfigure(1, weight=1)

                # Left: thumbnail (if available)
                thumb_label = ctk.CTkLabel(card, text="", width=160, height=90, fg_color="transparent")
                thumb_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(8, 8), pady=8)

                if getattr(video, "_thumbnail_bytes", None):
                    try:
                        bio = io.BytesIO(video._thumbnail_bytes)
                        img = Image.open(bio)
                        # resize to fit roughly within label
                        img.thumbnail((320, 180), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        # keep reference
                        self._image_refs[video.video_id or f"img_{idx}"] = photo
                        thumb_label.configure(image=photo, text="")
                    except Exception:
                        # fallback to text
                        thumb_label.configure(text="[thumbnail]")

                else:
                    # no thumbnail bytes: show placeholder text
                    thumb_label.configure(text="[thumbnail]")

                # Right: content (title, channel, stats)
                right = ctk.CTkFrame(card, fg_color="transparent")
                right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
                right.grid_columnconfigure(0, weight=1)

                title_lbl = ctk.CTkLabel(right, text=video.title or "Untitled", font=("Segoe UI", 14, "bold"), anchor="w", wraplength=600)
                title_lbl.grid(row=0, column=0, sticky="w")

                channel_text = video.channel_title or "Canal desconhecido"
                stats = []
                if video.views is not None:
                    stats.append(f"Views: {video.views:,}")
                if video.subscribers is not None:
                    stats.append(f"Inscritos: {video.subscribers:,}")
                if video.duration_seconds is not None:
                    mins, secs = divmod(video.duration_seconds, 60)
                    stats.append(f"Duração: {mins}m{secs}s")

                stats_lbl = ctk.CTkLabel(right, text=f"{channel_text}  •  {'  •  '.join(stats)}", anchor="w", text_color=self.theme.get("subtext_color"))
                stats_lbl.grid(row=1, column=0, sticky="w", pady=(6, 8))

                # Action buttons (preview/open)
                btn_frame = ctk.CTkFrame(card, fg_color="transparent")
                btn_frame.grid(row=1, column=1, sticky="e", padx=(0, 8), pady=(0, 8))

                preview_btn = ctk.CTkButton(btn_frame, text="Abrir no YouTube", width=140, height=30, corner_radius=8, command=lambda v=video: self._open_video(v))
                preview_btn.grid(row=0, column=0, padx=(6, 6))
            except Exception:
                logger.exception("Erro ao renderizar video %s", getattr(video, "video_id", None))

    def _open_video(self, video: Video):
        # Open the video URL in the default browser
        import webbrowser

        url = video.video_url or f"https://www.youtube.com/watch?v={video.video_id}"
        try:
            webbrowser.open(url)
        except Exception:
            logger.exception("Failed to open URL: %s", url)


# End of file
