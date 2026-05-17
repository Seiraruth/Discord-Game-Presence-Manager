 import os
 import logging
 import threading
 import time
+try:
+    import sip
+except ImportError:
+    sip = None
 from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox, QProgressDialog
 from PyQt5.QtGui import QIcon
 from PyQt5.QtCore import Qt
 from PyQt5.QtWidgets import QDialog
 from src.core.utils import ASSETS_DIR, LOG_FILE, set_autostart_windows
 from src.core.app_launcher import AppLauncher
 from src.ui.dialogs import MatchSelectionDialog, GamingMessageBox, GamingInputDialog, CustomPresenceDialog, AboutDialog, GAMING_STYLESHEET
 from src.ui.game_picker_window import GamePickerWindow
 from src.core.utils import get_lang_from_registry, load_locale
 
 try:
     LANG = get_lang_from_registry()
     TEXTS = load_locale(LANG)
 except Exception:
     LANG = os.getenv('DISCORD_PRESENCE_LANG', 'en')
     TEXTS = load_locale(LANG)
 
 logger = logging.getLogger('discord_presence_manager')
 
 class SystemTrayIcon(QSystemTrayIcon):
     def __init__(self, presence_manager, texts, config_manager, parent=None):
         super().__init__(parent)
         self.pm = presence_manager
         self.config_manager = config_manager
         TEXTS = texts
@@ -139,62 +143,79 @@ class SystemTrayIcon(QSystemTrayIcon):
         
         # Open Logs
         logs_action = QAction(TEXTS.get("tray_open_logs", "Open logs"), self.menu)
         logs_action.triggered.connect(self.open_logs)
         self.menu.addAction(logs_action)
 
         # About
         about_action = QAction(TEXTS.get("about", "About"), self.menu)
         about_action.triggered.connect(self.open_about)
         self.menu.addAction(about_action)
         
         self.menu.addSeparator()
         
         # Exit
         exit_action = QAction(TEXTS.get("tray_exit", "Exit"), self.menu)
         exit_action.triggered.connect(self.exit_app)
         self.menu.addAction(exit_action)
 
     def update_menu(self):
         self.create_menu()
 
     def on_activated(self, reason):
         if reason == QSystemTrayIcon.DoubleClick:
             self.open_game_picker()
 
-
-    def open_game_picker(self):
+    def _is_picker_deleted(self):
         if self.game_picker_window is None:
-            self.game_picker_window = GamePickerWindow(self.pm, self.config_manager, tray_icon=self)
-        elif not self.game_picker_window.isVisible() and self.game_picker_window.parent() is None:
-            # keep single instance but recover if somehow detached/invalid
-            self.game_picker_window = GamePickerWindow(self.pm, self.config_manager, tray_icon=self)
+            return True
+        if sip is not None:
+            try:
+                return sip.isdeleted(self.game_picker_window)
+            except Exception:
+                return False
+        return False
+
+    def _create_picker_window(self):
+        self.game_picker_window = GamePickerWindow(self.pm, self.config_manager, tray_icon=self)
+
+    def _show_and_activate_picker(self):
         self.game_picker_window.refresh_state_on_open()
         self.game_picker_window.show()
         self.game_picker_window.raise_()
         self.game_picker_window.activateWindow()
 
+    def open_game_picker(self):
+        if self.game_picker_window is None or self._is_picker_deleted():
+            self._create_picker_window()
+        try:
+            self._show_and_activate_picker()
+        except RuntimeError as exc:
+            logger.debug("Existing picker invalid during show/focus; recreating: %s", exc)
+            self._create_picker_window()
+            self._show_and_activate_picker()
+
     def toggle_start_windows(self, checked):
         self.config_manager.set_setting("start_with_windows", checked)
         set_autostart_windows(checked)
 
     def toggle_force_game(self):
         self.open_game_picker()
 
     def process_activity_simulator_input(self, game_name):
         """
         Similar to process_force_game but for activity simulator mode.
         Returns True if a game was successfully queued/started.
         """
         # Reuse search logic
         gm = self.pm.games_map or {}
         local_candidates = [k for k in gm if game_name.lower() in k.lower()]
         
         options = []
         if local_candidates:
             for k in local_candidates:
                 score = 1.0 if k.lower() == game_name.lower() else 0.8
                 options.append({"name": k, "id": gm[k].get("client_id"), "exe": gm[k].get("executable_path"), "score": score})
         
         discord_options = self.pm._find_discord_matches(game_name, max_candidates=50)
         for d_opt in discord_options:
             if not any(o["name"].lower() == d_opt["name"].lower() for o in options):
