#!/usr/bin/env python3
"""
Smart File Organizer - Desktop GUI Application
==============================================

Modern, attractive desktop application for managing the file organizer.
Uses CustomTkinter for a beautiful, modern UI.
"""

import sys
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    print("CustomTkinter not found. Install with: pip install customtkinter")
    sys.exit(1)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.actions.history_tracker import HistoryTracker
from src.actions.rules_engine import RulesEngine, MatchType


# Theme configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class StatsCard(ctk.CTkFrame):
    """A card widget for displaying statistics."""
    
    def __init__(self, master, title: str, value: str, icon: str = "📊", **kwargs):
        super().__init__(master, **kwargs)
        
        self.configure(
            corner_radius=15,
            fg_color=("#f0f0f0", "#2b2b2b"),
            border_width=1,
            border_color=("#e0e0e0", "#3b3b3b")
        )
        
        # Icon
        self.icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=ctk.CTkFont(size=32)
        )
        self.icon_label.pack(pady=(15, 5))
        
        # Value
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=("#1a73e8", "#60a5fa")
        )
        self.value_label.pack()
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        self.title_label.pack(pady=(0, 15))
    
    def update_value(self, value: str):
        self.value_label.configure(text=value)


class HistoryItem(ctk.CTkFrame):
    """A single history item widget."""
    
    def __init__(self, master, entry, undo_callback, **kwargs):
        super().__init__(master, **kwargs)
        
        self.entry = entry
        self.undo_callback = undo_callback
        
        self.configure(
            corner_radius=10,
            fg_color=("#ffffff", "#1f1f1f"),
            border_width=1,
            border_color=("#e8e8e8", "#333333")
        )
        
        # Main content frame
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=10)
        
        # Icon
        icon = "📁" if entry.can_undo else "✓"
        icon_label = ctk.CTkLabel(content, text=icon, font=ctk.CTkFont(size=20))
        icon_label.pack(side="left", padx=(0, 10))
        
        # File info
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        
        filename = Path(entry.source_path).name
        ctk.CTkLabel(
            info_frame,
            text=filename,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(fill="x")
        
        dest_short = f"→ {entry.category}/{entry.subcategory}" if entry.subcategory else f"→ {entry.category}"
        ctk.CTkLabel(
            info_frame,
            text=dest_short,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            anchor="w"
        ).pack(fill="x")
        
        # Time
        try:
            dt = datetime.fromisoformat(entry.timestamp)
            time_str = dt.strftime("%H:%M")
        except:
            time_str = ""
        
        ctk.CTkLabel(
            content,
            text=time_str,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(side="right", padx=(10, 0))
        
        # Undo button
        if entry.can_undo:
            undo_btn = ctk.CTkButton(
                content,
                text="Undo",
                width=60,
                height=28,
                corner_radius=6,
                fg_color=("#e3f2fd", "#1e3a5f"),
                text_color=("#1565c0", "#90caf9"),
                hover_color=("#bbdefb", "#2d4a6f"),
                command=lambda: self.undo_callback(entry.id)
            )
            undo_btn.pack(side="right", padx=5)


class RuleItem(ctk.CTkFrame):
    """A single rule item widget."""
    
    def __init__(self, master, rule, toggle_callback, delete_callback, **kwargs):
        super().__init__(master, **kwargs)
        
        self.rule = rule
        
        self.configure(
            corner_radius=10,
            fg_color=("#ffffff", "#1f1f1f"),
            border_width=1,
            border_color=("#e8e8e8", "#333333")
        )
        
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=10)
        
        # Toggle switch
        self.switch = ctk.CTkSwitch(
            content,
            text="",
            width=40,
            command=lambda: toggle_callback(rule.id, self.switch.get())
        )
        self.switch.pack(side="left", padx=(0, 10))
        if rule.enabled:
            self.switch.select()
        
        # Rule info
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            info_frame,
            text=rule.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(fill="x")
        
        pattern_text = f"Pattern: '{rule.pattern}' ({rule.match_type.value})"
        ctk.CTkLabel(
            info_frame,
            text=pattern_text,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            anchor="w"
        ).pack(fill="x")
        
        # Priority badge
        ctk.CTkLabel(
            content,
            text=f"P{rule.priority}",
            font=ctk.CTkFont(size=10),
            fg_color=("#e8f5e9", "#1b3d2f"),
            corner_radius=4,
            padx=6,
            pady=2
        ).pack(side="right", padx=5)
        
        # Delete button
        del_btn = ctk.CTkButton(
            content,
            text="🗑",
            width=30,
            height=28,
            corner_radius=6,
            fg_color=("#ffebee", "#3d1f1f"),
            text_color=("#c62828", "#ef9a9a"),
            hover_color=("#ffcdd2", "#4d2f2f"),
            command=lambda: delete_callback(rule.id)
        )
        del_btn.pack(side="right", padx=5)


class SmartOrganizerGUI(ctk.CTk):
    """Main GUI application for Smart File Organizer."""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Smart File Organizer")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        # Load config and components
        self.config = Config.load()
        self.history = HistoryTracker(base_directory=self.config.organization.base_directory)
        self.rules_engine = RulesEngine(base_directory=self.config.organization.base_directory)
        
        # Service status
        self._service_running = False
        
        # Build UI
        self._build_ui()
        
        # Auto-refresh
        self._refresh_data()
        self._schedule_refresh()
    
    def _build_ui(self):
        """Build the main UI."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self._build_sidebar()
        
        # Main content area
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)
        
        # Show dashboard by default
        self._show_dashboard()
    
    def _build_sidebar(self):
        """Build the sidebar navigation."""
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=("#f5f5f5", "#1a1a1a"))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(6, weight=1)
        
        # Logo/Title
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(
            logo_frame,
            text="🗂️",
            font=ctk.CTkFont(size=36)
        ).pack()
        
        ctk.CTkLabel(
            logo_frame,
            text="Smart File\nOrganizer",
            font=ctk.CTkFont(size=16, weight="bold"),
            justify="center"
        ).pack(pady=(5, 0))
        
        # Navigation buttons
        nav_buttons = [
            ("📊 Dashboard", self._show_dashboard),
            ("📜 History", self._show_history),
            ("⚙️ Rules", self._show_rules),
            ("🔧 Settings", self._show_settings),
        ]
        
        for text, command in nav_buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray20", "gray80"),
                hover_color=("#e0e0e0", "#2a2a2a"),
                command=command
            )
            btn.pack(fill="x", padx=10, pady=2)
        
        # Spacer
        ctk.CTkFrame(sidebar, fg_color="transparent", height=20).pack(fill="x")
        
        # Service control
        self.service_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        self.service_frame.pack(fill="x", padx=10, pady=10, side="bottom")
        
        self.status_label = ctk.CTkLabel(
            self.service_frame,
            text="● Running",
            font=ctk.CTkFont(size=12),
            text_color="#22c55e"
        )
        self.status_label.pack()
        
        btn_frame = ctk.CTkFrame(self.service_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Stop",
            width=70,
            height=30,
            corner_radius=6,
            fg_color=("#fee2e2", "#3f1f1f"),
            text_color=("#dc2626", "#f87171"),
            hover_color=("#fecaca", "#4f2f2f"),
            command=self._stop_service
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_frame,
            text="Restart",
            width=70,
            height=30,
            corner_radius=6,
            command=self._restart_service
        ).pack(side="right", padx=2)
        
        # Open dashboard link
        ctk.CTkButton(
            sidebar,
            text="🌐 Open Web Dashboard",
            height=35,
            corner_radius=8,
            fg_color=("#e0e7ff", "#1e3a5f"),
            text_color=("#4338ca", "#a5b4fc"),
            hover_color=("#c7d2fe", "#2d4a6f"),
            command=lambda: webbrowser.open("http://127.0.0.1:3000")
        ).pack(fill="x", padx=10, pady=10, side="bottom")
    
    def _clear_content(self):
        """Clear the content area."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def _show_dashboard(self):
        """Show the dashboard view."""
        self._clear_content()
        
        # Title
        ctk.CTkLabel(
            self.content_frame,
            text="Dashboard",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", pady=(0, 20))
        
        # Stats cards
        stats_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        stats_frame.pack(fill="x")
        
        stats = self.history.get_stats()
        
        cards_data = [
            ("Total Organized", str(stats.get("total_operations", 0)), "📁"),
            ("Undoable", str(stats.get("undoable", 0)), "↩️"),
            ("Categories", str(len(stats.get("by_category", {}))), "🏷️"),
            ("Total Size", f"{stats.get('total_size_bytes', 0) / 1024 / 1024:.1f} MB", "💾"),
        ]
        
        self.stat_cards = []
        for i, (title, value, icon) in enumerate(cards_data):
            card = StatsCard(stats_frame, title, value, icon)
            card.pack(side="left", padx=10, pady=10, expand=True, fill="both")
            self.stat_cards.append(card)
        
        # Recent activity
        ctk.CTkLabel(
            self.content_frame,
            text="Recent Activity",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", pady=(30, 10))
        
        # Activity list
        activity_scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            corner_radius=10,
            fg_color=("#fafafa", "#151515")
        )
        activity_scroll.pack(fill="both", expand=True)
        
        entries = self.history.get_recent(10)
        if entries:
            for entry in entries:
                item = HistoryItem(activity_scroll, entry, self._undo_entry)
                item.pack(fill="x", pady=3, padx=5)
        else:
            ctk.CTkLabel(
                activity_scroll,
                text="No activity yet. Drop a file in Downloads or Desktop!",
                font=ctk.CTkFont(size=13),
                text_color=("gray50", "gray60")
            ).pack(pady=50)
    
    def _show_history(self):
        """Show the history view."""
        self._clear_content()
        
        # Title with undo all button
        header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header,
            text="Organization History",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        
        ctk.CTkButton(
            header,
            text="Undo Last",
            width=100,
            corner_radius=8,
            command=self._undo_last
        ).pack(side="right")
        
        # History list
        history_scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            corner_radius=10,
            fg_color=("#fafafa", "#151515")
        )
        history_scroll.pack(fill="both", expand=True)
        
        entries = self.history.get_recent(50)
        if entries:
            for entry in entries:
                item = HistoryItem(history_scroll, entry, self._undo_entry)
                item.pack(fill="x", pady=3, padx=5)
        else:
            ctk.CTkLabel(
                history_scroll,
                text="No history yet.",
                font=ctk.CTkFont(size=13),
                text_color=("gray50", "gray60")
            ).pack(pady=50)
    
    def _show_rules(self):
        """Show the rules management view."""
        self._clear_content()
        
        # Title with add button
        header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header,
            text="Custom Rules",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        
        ctk.CTkButton(
            header,
            text="+ Add Rule",
            width=100,
            corner_radius=8,
            command=self._show_add_rule_dialog
        ).pack(side="right")
        
        # Rules list
        rules_scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            corner_radius=10,
            fg_color=("#fafafa", "#151515")
        )
        rules_scroll.pack(fill="both", expand=True)
        
        rules = self.rules_engine.get_rules()
        if rules:
            for rule in sorted(rules, key=lambda r: -r.priority):
                item = RuleItem(
                    rules_scroll,
                    rule,
                    self._toggle_rule,
                    self._delete_rule
                )
                item.pack(fill="x", pady=3, padx=5)
        else:
            ctk.CTkLabel(
                rules_scroll,
                text="No custom rules. Click '+ Add Rule' to create one.",
                font=ctk.CTkFont(size=13),
                text_color=("gray50", "gray60")
            ).pack(pady=50)
    
    def _show_settings(self):
        """Show the settings view."""
        self._clear_content()
        
        ctk.CTkLabel(
            self.content_frame,
            text="Settings",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", pady=(0, 20))
        
        settings_frame = ctk.CTkScrollableFrame(
            self.content_frame,
            corner_radius=10,
            fg_color=("#fafafa", "#151515")
        )
        settings_frame.pack(fill="both", expand=True)
        
        # Watch directories
        self._add_setting_section(settings_frame, "Watch Directories", [
            f"📁 {d}" for d in self.config.watcher.watch_directories
        ])
        
        # Organization settings
        org_items = [
            f"In-place: {'Yes' if self.config.organization.organize_in_place else 'No'}",
            f"Base directory: {self.config.organization.base_directory}",
            f"Date folders: {'Yes' if self.config.organization.use_date_folders else 'No'}",
        ]
        self._add_setting_section(settings_frame, "Organization", org_items)
        
        # Classification
        class_items = [
            f"LLM Model: {self.config.classification.llm_model}",
            f"OCR: {'Enabled' if self.config.classification.ocr_enabled else 'Disabled'}",
        ]
        self._add_setting_section(settings_frame, "Classification", class_items)
        
        # Deduplication
        dedup_items = [
            f"Enabled: {'Yes' if self.config.deduplication.enabled else 'No'}",
            f"Duplicate action: {self.config.deduplication.duplicate_action}",
        ]
        self._add_setting_section(settings_frame, "Deduplication", dedup_items)
        
        # Config file button
        ctk.CTkButton(
            settings_frame,
            text="📝 Open config.yaml",
            corner_radius=8,
            command=lambda: webbrowser.open(str(Path.cwd() / "config.yaml"))
        ).pack(pady=20)
    
    def _add_setting_section(self, parent, title: str, items: list):
        """Add a settings section."""
        section = ctk.CTkFrame(parent, fg_color=("#ffffff", "#1f1f1f"), corner_radius=10)
        section.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            section,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))
        
        for item in items:
            ctk.CTkLabel(
                section,
                text=item,
                font=ctk.CTkFont(size=12),
                text_color=("gray40", "gray70")
            ).pack(anchor="w", padx=15, pady=2)
        
        ctk.CTkFrame(section, height=10, fg_color="transparent").pack()
    
    def _show_add_rule_dialog(self):
        """Show dialog to add a new rule."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Custom Rule")
        dialog.geometry("400x400")
        dialog.transient(self)
        dialog.grab_set()
        
        # Form fields
        ctk.CTkLabel(dialog, text="Rule Name:").pack(anchor="w", padx=20, pady=(20, 5))
        name_entry = ctk.CTkEntry(dialog, width=360)
        name_entry.pack(padx=20)
        
        ctk.CTkLabel(dialog, text="Pattern:").pack(anchor="w", padx=20, pady=(15, 5))
        pattern_entry = ctk.CTkEntry(dialog, width=360)
        pattern_entry.pack(padx=20)
        
        ctk.CTkLabel(dialog, text="Category:").pack(anchor="w", padx=20, pady=(15, 5))
        category_entry = ctk.CTkEntry(dialog, width=360)
        category_entry.insert(0, "Documents")
        category_entry.pack(padx=20)
        
        ctk.CTkLabel(dialog, text="Subcategory:").pack(anchor="w", padx=20, pady=(15, 5))
        subcategory_entry = ctk.CTkEntry(dialog, width=360)
        subcategory_entry.pack(padx=20)
        
        ctk.CTkLabel(dialog, text="Priority (1-100):").pack(anchor="w", padx=20, pady=(15, 5))
        priority_entry = ctk.CTkEntry(dialog, width=360)
        priority_entry.insert(0, "50")
        priority_entry.pack(padx=20)
        
        def save_rule():
            self.rules_engine.add_rule(
                name=name_entry.get(),
                pattern=pattern_entry.get(),
                category=category_entry.get(),
                subcategory=subcategory_entry.get(),
                priority=int(priority_entry.get() or 50)
            )
            dialog.destroy()
            self._show_rules()
        
        ctk.CTkButton(
            dialog,
            text="Save Rule",
            width=200,
            corner_radius=8,
            command=save_rule
        ).pack(pady=30)
    
    def _undo_entry(self, entry_id: int):
        """Undo a specific entry."""
        self.history.undo_by_id(entry_id)
        self._refresh_data()
        self._show_dashboard()
    
    def _undo_last(self):
        """Undo the last operation."""
        self.history.undo_last()
        self._refresh_data()
        self._show_history()
    
    def _toggle_rule(self, rule_id: int, enabled: bool):
        """Toggle a rule on/off."""
        self.rules_engine.enable_rule(rule_id, enabled)
    
    def _delete_rule(self, rule_id: int):
        """Delete a rule."""
        self.rules_engine.remove_rule(rule_id)
        self._show_rules()
    
    def _stop_service(self):
        """Stop the systemd service."""
        import subprocess
        subprocess.run(["systemctl", "--user", "stop", "smart-file-organizer"])
        self.status_label.configure(text="● Stopped", text_color="#ef4444")
    
    def _restart_service(self):
        """Restart the systemd service."""
        import subprocess
        subprocess.run(["systemctl", "--user", "restart", "smart-file-organizer"])
        self.status_label.configure(text="● Running", text_color="#22c55e")
    
    def _refresh_data(self):
        """Refresh data from disk."""
        self.history = HistoryTracker(base_directory=self.config.organization.base_directory)
        self.rules_engine = RulesEngine(base_directory=self.config.organization.base_directory)
    
    def _schedule_refresh(self):
        """Schedule periodic data refresh."""
        self._refresh_data()
        self.after(10000, self._schedule_refresh)  # Every 10 seconds


def main():
    """Launch the GUI application."""
    app = SmartOrganizerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
