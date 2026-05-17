import difflib
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt, QTimer, QSize, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox
)

from src.core.game_art_resolver import GameArtResolver

logger = logging.getLogger('discord_presence_manager')

@dataclass
class GameEntry:
    name: str
    id: str = ""
    executable_path: str = ""
    steam_appid: str = ""
    source: str = "Local"

class WorkerSignals(QObject):
    done = pyqtSignal(dict, object)

class ArtJob(QRunnable):
    def __init__(self, resolver, game, signals):
        super().__init__()
        self.resolver = resolver
        self.game = game
        self.signals = signals
    def run(self):
        path = self.resolver.resolve(self.game)
        self.signals.done.emit(self.game, path)

class GamePickerWindow(QDialog):
    def __init__(self, pm, config_manager, tray_icon=None, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.config_manager = config_manager
        self.tray_icon = tray_icon
        self.resolver = GameArtResolver(config_manager)
        self.thread_pool = QThreadPool.globalInstance()
        self.recent = config_manager.get_setting("recent_forced_games", []) or []
        self.entries: List[GameEntry] = []
        self._by_name: Dict[str, GameEntry] = {}
        self._icon_cache: Dict[Tuple[str, str, str], object] = {}
        self._visible_keys = set()
        self._in_flight_art = set()
        self._last_games_signature = None

        self.setWindowTitle("Force Game")
        self.resize(980, 700)
        self.setStyleSheet("QDialog{background:#1e1f22;color:#dcddde;} QLineEdit{background:#2b2d31;color:#fff;padding:8px;border:1px solid #444;} QListWidget{background:#1e1f22;border:1px solid #333;} QPushButton{background:#2b2d31;color:#fff;padding:8px;} QPushButton:hover{background:#3b3d42;}")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h2>Force Game</h2>"))
        self.search = QLineEdit(); self.search.setPlaceholderText("Search games...")
        lay.addWidget(self.search)
        self.status = QLabel("Active game: none")
        lay.addWidget(self.status)
        self.results_status = QLabel("Showing 0 of 0")
        lay.addWidget(self.results_status)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(160, 220))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(10)
        lay.addWidget(self.list, 1)

        btns = QHBoxLayout()
        self.stop_btn = QPushButton("Stop Current Presence")
        self.sync_btn = QPushButton("Sync Games")
        self.refresh_btn = QPushButton("Refresh Covers")
        self.close_btn = QPushButton("Close")
        for b in (self.stop_btn, self.sync_btn, self.refresh_btn, self.close_btn): btns.addWidget(b)
        lay.addLayout(btns)

        self.search_timer = QTimer(self); self.search_timer.setSingleShot(True); self.search_timer.setInterval(180)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self.apply_filter)
        self.list.itemClicked.connect(self.force_from_item)
        self.list.itemDoubleClicked.connect(lambda item: self.force_from_item(item, minimize=True))
        self.stop_btn.clicked.connect(self.stop_presence)
        self.sync_btn.clicked.connect(self.sync_games)
        self.refresh_btn.clicked.connect(self.refresh_covers)
        self.close_btn.clicked.connect(self.close)
        if hasattr(self.pm, "sync_finished"):
            self.pm.sync_finished.connect(self._on_sync_finished)

        self.load_games()
        self.apply_filter()
        self.refresh_state_on_open()

    def load_games(self):
        self.entries = []
        self._by_name = {}
        gm = self.pm.games_map or {}
        for name, data in gm.items():
            e = GameEntry(name=name, id=str(data.get("client_id") or ""), executable_path=data.get("executable_path") or "", steam_appid=str(data.get("steam_appid") or ""), source="Local")
            self.entries.append(e); self._by_name[name.lower()] = e
        for d in self.pm._fetch_discord_apps_cached(force_download=False) or []:
            name = d.get("name")
            if name and name.lower() not in self._by_name:
                e = GameEntry(name=name, id=str(d.get("id") or ""), source="Discord")
                self.entries.append(e); self._by_name[name.lower()] = e
        self._last_games_signature = self._games_signature()

    def _rank(self, name, q):
        n, ql = name.lower(), q.lower()
        if not ql: return 100 if n in [x.lower() for x in self.recent] else 0
        if n == ql: return 1000
        if n.startswith(ql): return 900
        if ql in n: return 700
        short = ''.join(ch for ch in n if ch.isalnum())
        if all(ch in short for ch in ql): return 500
        return int(difflib.SequenceMatcher(None, ql, n).ratio()*100)

    def apply_filter(self):
        q = self.search.text().strip()
        ranked = sorted(self.entries, key=lambda e: self._rank(e.name, q), reverse=True)
        total = len(self.entries)
        self.list.clear()
        shown = 0
        self._visible_keys = set()
        for e in ranked[:300]:
            if q and self._rank(e.name, q) < 35: continue
            item = QListWidgetItem(f"{e.name}\n{e.source}")
            item.setData(Qt.UserRole, e)
            key = self._entry_key(e)
            self._visible_keys.add(key)
            cached_icon = self._icon_cache.get(key)
            item.setIcon(cached_icon if cached_icon else self._placeholder_icon(e.name))
            self.list.addItem(item)
            shown += 1
            if not cached_icon:
                self._queue_cover(item, e)
        self.results_status.setText(f"Showing {shown} of {total}")

    def _placeholder_icon(self, name):
        pix = QPixmap(160, 220); pix.fill(QColor("#2b2d31"))
        p = QPainter(pix); p.setPen(QColor("#cfd2d6")); p.drawText(pix.rect().adjusted(10,10,-10,-10), Qt.AlignCenter | Qt.TextWordWrap, name[:45]); p.end()
        from PyQt5.QtGui import QIcon
        return QIcon(pix)

    def _queue_cover(self, item, entry):
        key = self._entry_key(entry)
        cached_icon = self._icon_cache.get(key)
        if cached_icon:
            item.setIcon(cached_icon)
            return
        if key in self._in_flight_art:
            return
        self._in_flight_art.add(key)
        signals = WorkerSignals()
        signals.done.connect(lambda game, path, it=item, k=key: self._set_cover(it, path, game, k))
        self.thread_pool.start(ArtJob(self.resolver, entry.__dict__, signals))

    def _set_cover(self, item, path, game, key):
        self._in_flight_art.discard(key)
        if not path: return
        pix = QPixmap(str(path))
        if pix.isNull(): return
        from PyQt5.QtGui import QIcon
        icon = QIcon(pix.scaled(160,220,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
        self._icon_cache[key] = icon
        if key not in self._visible_keys:
            return
        row = self.list.row(item)
        if row < 0:
            return
        e = item.data(Qt.UserRole)
        if not e or self._entry_key(e) != key:
            return
        item.setIcon(icon)

    def force_from_item(self, item, minimize=False):
        if self.tray_icon is None:
            logger.error("Tray integration unavailable in force_from_item; cannot force game.")
            QMessageBox.warning(self, "Force Game", "Tray integration is unavailable. Cannot force game from picker.")
            return
        e: GameEntry = item.data(Qt.UserRole)
        try:
            match = {"name": e.name, "id": e.id, "exe": e.executable_path or f"{e.name}.exe", "steam_appid": e.steam_appid}
            self.tray_icon.apply_force_game(match)
            self.status.setText(f"Active game: {e.name}")
            self._push_recent(e.name)
            if minimize:
                self.close()
        except Exception as ex:
            logger.exception("Error forcing game")
            QMessageBox.warning(self, "Force Game", f"Failed to force game: {ex}")

    def _push_recent(self, name):
        cur = [x for x in self.recent if x.lower() != name.lower()]
        cur.insert(0, name)
        self.recent = cur[:20]
        self.config_manager.set_setting("recent_forced_games", self.recent)

    def stop_presence(self):
        self.pm.stop_force_game()
        self.status.setText("Active game: none")

    def refresh_covers(self):
        self._icon_cache.clear()
        self._in_flight_art.clear()
        if hasattr(self.resolver, "clear_cache"):
            try:
                self.resolver.clear_cache()
            except Exception:
                logger.exception("Failed to clear art resolver cache safely")
        self.apply_filter()

    def sync_games(self):
        if self.tray_icon is None:
            QMessageBox.warning(self, "Force Game", "Tray integration is unavailable. Sync cannot be started.")
            return
        self.tray_icon.sync_games()

    def _on_sync_finished(self, updated, total):
        del updated, total
        self.refresh_state_on_open()

    def refresh_state_on_open(self):
        try:
            active = self.pm.forced_game or self.pm.last_game or {}
            self.status.setText(f"Active game: {active.get('name', 'none')}")
        except Exception:
            logger.exception("Failed to refresh active game status")
            self.status.setText("Active game: none")

        try:
            self.recent = self.config_manager.get_setting("recent_forced_games", []) or []
        except Exception:
            logger.exception("Failed to reload recent games")
            self.recent = []

        try:
            if self._games_signature() != self._last_games_signature:
                self.load_games()
        except Exception:
            logger.exception("Failed to detect/reload changed game map")

        try:
            self.apply_filter()
        except Exception:
            logger.exception("Failed to apply filter during refresh_state_on_open")

        try:
            if self.config_manager.get_setting("remember_window_size", True):
                size = self.config_manager.get_setting("game_picker_size", [])
                if isinstance(size, list) and len(size) == 2:
                    w, h = int(size[0]), int(size[1])
                    if 600 <= w <= 3840 and 400 <= h <= 2160:
                        self.resize(w, h)
        except Exception:
            logger.exception("Failed to restore remembered game picker size")

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close(); return
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and self.list.count() == 1:
            self.force_from_item(self.list.item(0)); return
        super().keyPressEvent(ev)

    def closeEvent(self, ev):
        if self.config_manager.get_setting("remember_window_size", True):
            self.config_manager.set_setting("game_picker_size", [self.width(), self.height()])
        if self.config_manager.get_setting("minimize_to_tray_on_close", True):
            ev.accept()
            self.hide()
            return
        super().closeEvent(ev)

    def _entry_key(self, entry: GameEntry) -> Tuple[str, str, str]:
        return (entry.name.lower().strip(), str(entry.steam_appid or "").strip(), str(entry.id or "").strip())

    def _games_signature(self):
        gm = self.pm.games_map or {}
        return tuple(sorted((k.lower(), str((v or {}).get("client_id") or ""), str((v or {}).get("steam_appid") or "")) for k, v in gm.items()))
