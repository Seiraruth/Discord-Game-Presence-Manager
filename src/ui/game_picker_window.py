import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt, QTimer, QSize, QRunnable, QThreadPool, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QRect
from PyQt5.QtGui import QPixmap, QPainter, QColor, QImage, QIcon, QPainterPath
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QGraphicsDropShadowEffect, QWidget, QStyledItemDelegate, QStyle
)
from rapidfuzz import fuzz

from src.core.game_art_resolver import GameArtResolver

logger = logging.getLogger('discord_presence_manager')

class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("titleBarWidget")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        
        self.title_label = QLabel("Discord Presence Manager")
        self.title_label.setObjectName("titleBarLabel")
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("titleBarBtn")
        self.min_btn.setFixedSize(30, 24)
        self.min_btn.clicked.connect(self.window().showMinimized)
        layout.addWidget(self.min_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("titleBarCloseBtn")
        self.close_btn.setFixedSize(30, 24)
        self.close_btn.clicked.connect(self.window().close)
        layout.addWidget(self.close_btn)
        
        self.start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.start_pos is not None:
            delta = event.globalPos() - self.start_pos
            self.window().move(self.window().pos() + delta)
            self.start_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.start_pos = None

@dataclass
class GameEntry:
    name: str
    id: str = ""
    executable_path: str = ""
    steam_appid: str = ""
    source: str = "Local"

class DiscordCacheSignals(QObject):
    done = pyqtSignal(list)

class DiscordCacheJob(QRunnable):
    def __init__(self, pm, force_download, signals):
        super().__init__()
        self.pm = pm
        self.force_download = force_download
        self.signals = signals
    def run(self):
        apps = self.pm._fetch_discord_apps_cached(force_download=self.force_download)
        self.signals.done.emit(apps or [])

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
        qimage = None
        if path:
            qimage = QImage(str(path))
            if not qimage.isNull():
                qimage = qimage.scaled(160, 220, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                qimage = apply_rounded_corners(qimage, 8)
            else:
                qimage = None
                
        if qimage is None:
            game_name = self.game.get("name", "Unknown Game") if isinstance(self.game, dict) else getattr(self.game, "name", "Unknown Game")
            qimage = get_placeholder_cover(game_name)
            
        self.signals.done.emit(self.game, qimage)

def get_placeholder_cover(game_name):
    target = QImage(160, 220, QImage.Format_ARGB32_Premultiplied)
    target.fill(Qt.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, 160, 220, 8, 8)
    painter.setClipPath(path)
    painter.fillRect(0, 0, 160, 220, QColor("#232428"))
    
    pen = painter.pen()
    pen.setColor(QColor("#9a9aa2"))
    pen.setWidth(2)
    painter.setPen(pen)
    
    # Generic gamepad drawing
    painter.drawRoundedRect(40, 80, 80, 40, 20, 20)
    painter.drawEllipse(50, 95, 10, 10)
    painter.drawEllipse(60, 85, 10, 10)
    painter.drawEllipse(90, 95, 10, 10)
    painter.drawEllipse(100, 85, 10, 10)
    
    font = painter.font()
    font.setPointSize(9)
    painter.setFont(font)
    text_rect = QRect(10, 140, 140, 60)
    painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, game_name)
    
    painter.end()
    return target

def apply_rounded_corners(img: QImage, radius: int) -> QImage:
    target = QImage(img.size(), QImage.Format_ARGB32_Premultiplied)
    target.fill(Qt.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, img.width(), img.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawImage(0, 0, img)
    painter.end()
    return target

def create_search_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = painter.pen()
    pen.setColor(QColor("#9a9aa2"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawEllipse(2, 2, 8, 8)
    painter.drawLine(9, 9, 14, 14)
    painter.end()
    return QIcon(pixmap)

class GameItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2b2d31"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#232428"))
            
        rect = option.rect
        entry = index.data(Qt.UserRole)
        icon = index.data(Qt.DecorationRole)
        title = entry.name if entry else ""
        source = entry.source if entry else ""
        
        if icon:
            pixmap = icon.pixmap(160, 220)
            x = rect.x() + (rect.width() - 160) // 2
            y = rect.y() + 8
            painter.drawPixmap(x, y, pixmap)
            
        painter.setPen(QColor("#e8e8ea"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        text_rect = QRect(rect.x(), rect.y() + 235, rect.width(), 20)
        fm = painter.fontMetrics()
        elided = fm.elidedText(title, Qt.ElideRight, rect.width() - 10)
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, elided)
        
        pill_width = 50
        pill_height = 18
        px = rect.x() + (rect.width() - pill_width) // 2
        py = text_rect.bottom() + 4
        bg_color = QColor("#5865f2") if source.lower() == "discord" or source.lower() == "steam" else QColor("#3b3d42")
        
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(px, py, pill_width, pill_height, 9, 9)
        
        painter.setPen(QColor("#ffffff"))
        pill_font = painter.font()
        pill_font.setPointSize(7)
        pill_font.setBold(True)
        painter.setFont(pill_font)
        painter.drawText(px, py, pill_width, pill_height, Qt.AlignCenter, source.upper())
        
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(170, 290)

class GamePickerWindow(QDialog):
    def __init__(self, pm, config_manager, tray_icon=None, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.config_manager = config_manager
        self.tray_icon = tray_icon
        self.entries: List[GameEntry] = []
        self.recent = []
        self._loaded = False
        self._loading = False
        self._game_signature = None
        self._icon_cache: Dict[Tuple[str, str, str], object] = {}
        self._in_flight_art = set()
        self._pending_cover_items = []
        self._cover_batch_timer = QTimer(self)
        self._cover_batch_timer.setInterval(100)
        self._cover_batch_timer.timeout.connect(self._process_cover_batch)
        self._max_visible_results = int(self._get_setting("game_picker_max_visible_results", 120) or 120)
        self._search_limit = int(self._get_setting("game_picker_search_limit", 60) or 60)
        self._empty_limit = int(self._get_setting("game_picker_empty_limit", 40) or 40)
        self._cover_initial_batch_size = int(self._get_setting("game_art_initial_batch_size", 8) or 8)
        self._cover_batch_size = int(self._get_setting("game_art_batch_size", 4) or 4)
        self._load_discord_cache_on_startup = bool(self._get_setting("load_discord_cache_on_startup", False))

        self.resolver = GameArtResolver(config_manager)
        self.thread_pool = QThreadPool.globalInstance()
        self.recent = self._get_setting("recent_forced_games", []) or []
        self._by_name: Dict[str, GameEntry] = {}
        self._visible_keys = set()
        self._last_games_signature = None
        self._discord_entries_loaded = False

        self.setWindowTitle("Force Game")
        self.resize(980, 700)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        self.title_bar = TitleBar(self)
        main_lay.addWidget(self.title_bar)
        
        content_widget = QWidget()
        lay = QVBoxLayout(content_widget)
        lay.setContentsMargins(24, 24, 24, 32)
        lay.setSpacing(16)
        
        main_lay.addWidget(content_widget, 1)
        
        title_label = QLabel("Force Game")
        title_label.setObjectName("titleLabel")
        lay.addWidget(title_label)
        
        self.search = QLineEdit(); self.search.setPlaceholderText("Search games...")
        self.search.addAction(create_search_icon(), QLineEdit.LeadingPosition)
        
        # Add subtle drop shadow to search bar
        shadow_search = QGraphicsDropShadowEffect()
        shadow_search.setBlurRadius(20)
        shadow_search.setYOffset(2)
        shadow_search.setColor(QColor(0, 0, 0, 70))
        self.search.setGraphicsEffect(shadow_search)
        
        lay.addWidget(self.search)
        
        self.status = QLabel("Loading games...")
        self.status.setObjectName("statusLabel")
        lay.addWidget(self.status)
        self.results_status = QLabel("Showing 0 of 0")
        self.results_status.setObjectName("resultsStatusLabel")
        lay.addWidget(self.results_status)

        self.list = QListWidget()
        self.list.setItemDelegate(GameItemDelegate(self.list))
        
        # Add subtle drop shadow to list widget
        shadow_list = QGraphicsDropShadowEffect()
        shadow_list.setBlurRadius(20)
        shadow_list.setYOffset(2)
        shadow_list.setColor(QColor(0, 0, 0, 70))
        self.list.setGraphicsEffect(shadow_list)
        
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

        self.search_timer = QTimer(self); self.search_timer.setSingleShot(True); self.search_timer.setInterval(250)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self.apply_filter)
        self._visible_cover_timer = QTimer(self)
        self._visible_cover_timer.setSingleShot(True)
        self._visible_cover_timer.setInterval(150)
        self._visible_cover_timer.timeout.connect(self._load_visible_covers)
        self.list.verticalScrollBar().valueChanged.connect(self._schedule_visible_cover_load)
        self.list.itemClicked.connect(self.force_from_item)
        self.list.itemDoubleClicked.connect(lambda item: self.force_from_item(item, minimize=True))
        self.stop_btn.clicked.connect(self.stop_presence)
        self.sync_btn.clicked.connect(self.sync_games)
        self.refresh_btn.clicked.connect(self.refresh_covers)
        self.close_btn.clicked.connect(self.close)
        if hasattr(self.pm, "sync_finished"):
            self.pm.sync_finished.connect(self._on_sync_finished)

        logger.debug("Game picker UI constructed")
        QTimer.singleShot(0, self.initial_load)

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(150)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_anim.start()

    def _get_setting(self, key, default=None):
        try:
            if hasattr(self.config_manager, "get_setting"):
                return self.config_manager.get_setting(key, default)
            settings = getattr(self.config_manager, "app_settings", {}) or {}
            return settings.get(key, default)
        except Exception:
            return default

    def initial_load(self):
        if self._loading or self._loaded:
            return
        self._loading = True
        self.status.setText("Loading games...")
        try:
            t0 = time.perf_counter()
            self.load_local_games()
            self._loaded = True
            logger.debug("Game picker loaded %s local games in %.2fs", len(self.entries), time.perf_counter() - t0)
            self.apply_filter()
            self.refresh_state_on_open()
            if self._load_discord_cache_on_startup:
                self.load_discord_cache_async()
        except Exception:
            logger.exception("Failed to load game picker data")
            self.status.setText("Failed to load games.")
        finally:
            self._loading = False

    def load_local_games(self):
        self.entries = []
        self._by_name = {}
        gm = self.pm.games_map or {}
        for name, data in gm.items():
            e = GameEntry(name=name, id=str(data.get("client_id") or ""), executable_path=data.get("executable_path") or "", steam_appid=str(data.get("steam_appid") or ""), source="Local")
            self.entries.append(e); self._by_name[name.lower()] = e
        self._last_games_signature = self._games_signature()

    def load_discord_cache_async(self):
        if self._discord_entries_loaded:
            return
        signals = DiscordCacheSignals()
        signals.done.connect(self._on_discord_cache_loaded)
        self.thread_pool.start(DiscordCacheJob(self.pm, False, signals))

    def _on_discord_cache_loaded(self, apps):
        t0 = time.perf_counter()
        for d in apps:
            name = d.get("name")
            if name and name.lower() not in self._by_name:
                e = GameEntry(name=name, id=str(d.get("id") or ""), source="Discord")
                self.entries.append(e); self._by_name[name.lower()] = e
        self._discord_entries_loaded = True
        logger.debug("Game picker loaded discord cache entries in %.2fs (total entries=%s)", time.perf_counter() - t0, len(self.entries))
        self.apply_filter()
        self._last_games_signature = self._games_signature()

    def _rank(self, name, q):
        n, ql = name.lower(), q.lower()
        if not ql: return 100 if n in [x.lower() for x in self.recent] else 0
        if n == ql: return 1000
        if n.startswith(ql): return 900
        if any(part.startswith(ql) for part in n.split()): return 800
        if ql in n: return 700
        if len(ql) <= 2:
            return 0
        short = ''.join(ch for ch in n if ch.isalnum())
        if all(ch in short for ch in ql): return 500
        return int(fuzz.WRatio(ql, n))

    # TODO: For better scalability, migrate to QListView + QAbstractListModel + custom delegate virtualization.
    def apply_filter(self):
        if not hasattr(self, "_max_visible_results"):
            self._max_visible_results = 120
        if not self.entries:
            self.list.clear()
            self.results_status.setText("Showing 0 of 0")
            self.status.setText("Loading games..." if self._loading else "No games loaded.")
            return
        q = self.search.text().strip()
        ql = q.lower()
        t0 = time.perf_counter()
        ranked = []
        matched_count = 0
        mode = "search" if q else "empty"
        if not q:
            recent_lower = {x.lower() for x in (self.recent or [])}
            recent_ranked = []
            others = []
            for e in self.entries:
                nl = e.name.lower()
                if nl in recent_lower:
                    recent_ranked.append((1000, e))
                else:
                    others.append((100, e))
            ranked = recent_ranked + others
            matched_count = len(self.entries)
        else:
            for e in self.entries:
                score = self._rank(e.name, q)
                if score < 35:
                    continue
                matched_count += 1
                ranked.append((score, e))
            ranked.sort(key=lambda x: x[0], reverse=True)
            
        total = len(self.entries)
        render_limit = self._max_visible_results
        self.list.clear()
        self._cover_batch_timer.stop()
        self._visible_cover_timer.stop()
        self._pending_cover_items.clear()
        shown = 0
        self._visible_keys = set()
        self.list.setUpdatesEnabled(False)
        try:
            for _, e in ranked[:render_limit]:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, e)
                key = self._entry_key(e)
                item.setData(Qt.UserRole + 1, key)
                self._visible_keys.add(key)
                cached_icon = self._icon_cache.get(key)
                item.setIcon(cached_icon if cached_icon else self._placeholder_icon(e.name))
                self.list.addItem(item)
                shown += 1
                if not cached_icon:
                    self._pending_cover_items.append((item, e))
        finally:
            self.list.setUpdatesEnabled(True)
            
        if q:
            self.results_status.setText(f"Showing {shown} of {matched_count} matches · Library: {total}")
        else:
            self.results_status.setText(f"Showing {shown} games · Library: {total}")
            self.status.setText(f"Type to search {total} games")
            
        elapsed = time.perf_counter() - t0
        logger.debug("Game picker filter mode=%s query=%r limit=%s matched=%s shown=%s total=%s duration=%.3fs", mode, q, render_limit, matched_count, shown, total, elapsed)
        self._schedule_visible_cover_load(initial=True)
        
        if self._pending_cover_items:
            initial = self._pending_cover_items[:self._cover_initial_batch_size]
            self._pending_cover_items = self._pending_cover_items[self._cover_initial_batch_size:]
            for item, e in initial:
                self._queue_cover(item, e)
                
        if self._pending_cover_items and not self._cover_batch_timer.isActive():
            self._cover_batch_timer.start()

    def _process_cover_batch(self):
        t0 = time.perf_counter()
        batch = self._pending_cover_items[:self._cover_batch_size]
        self._pending_cover_items = self._pending_cover_items[self._cover_batch_size:]
        for item, entry in batch:
            self._queue_cover(item, entry)
        if not self._pending_cover_items:
            self._cover_batch_timer.stop()
        logger.debug("Game picker queued %s cover jobs in %.3fs", len(batch), time.perf_counter() - t0)

    def _schedule_visible_cover_load(self, initial=False):
        if initial:
            self._visible_cover_timer.start(50)
        else:
            self._visible_cover_timer.start()

    def _load_visible_covers(self):
        viewport = self.list.viewport()
        visible_candidates = []
        queued_count = 0
        
        first_item = self.list.itemAt(0, 0)
        last_item = self.list.itemAt(viewport.width(), viewport.height())
        
        start_row = self.list.row(first_item) if first_item else 0
        end_row = self.list.row(last_item) if last_item else self.list.count() - 1
        if end_row < 0:
            end_row = self.list.count() - 1
            
        for i in range(start_row, min(end_row + 1, self.list.count())):
            item = self.list.item(i)
            if not item:
                continue
            key = item.data(Qt.UserRole + 1)
            entry = item.data(Qt.UserRole)
            if not key or not entry:
                continue
            cached = self._icon_cache.get(key)
            if cached:
                item.setIcon(cached)
                continue
            if key in self._in_flight_art:
                continue
            visible_candidates.append((item, entry))

        if visible_candidates:
            first = visible_candidates[:self._cover_initial_batch_size]
            rest = visible_candidates[self._cover_initial_batch_size:]
            for item, entry in first:
                self._queue_cover(item, entry)
                queued_count += 1
            self._pending_cover_items = rest
            if self._pending_cover_items and not self._cover_batch_timer.isActive():
                self._cover_batch_timer.start()
        logger.debug("Queued %s visible cover jobs; pending=%s in_flight=%s", queued_count, len(self._pending_cover_items), len(self._in_flight_art))

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
        signals.done.connect(lambda game, qimage, k=key: self._set_cover_by_key(qimage, game, k))
        self.thread_pool.start(ArtJob(self.resolver, entry.__dict__, signals))

    def _find_item_by_cover_key(self, key):
        for i in range(self.list.count()):
            item = self.list.item(i)
            try:
                if item and item.data(Qt.UserRole + 1) == key:
                    return item
            except RuntimeError:
                continue
        return None

    def _set_cover_by_key(self, qimage, game, key):
        del game
        try:
            self._in_flight_art.discard(key)
            if qimage is None:
                return
            item = self._find_item_by_cover_key(key)
            if item is None:
                return
            current_entry = item.data(Qt.UserRole)
            if not current_entry:
                return
            current_key = item.data(Qt.UserRole + 1)
            if current_key != key:
                return
            icon = self._icon_cache.get(key)
            if icon is None:
                pix = QPixmap.fromImage(qimage)
                if pix.isNull():
                    return
                icon = QIcon(pix)
                self._icon_cache[key] = icon
            item.setIcon(icon)
        except RuntimeError:
            logger.debug("Ignoring stale cover update for deleted item/key=%s", key)
        except Exception:
            logger.exception("Failed to apply cover art for key=%s", key)

    def _set_cover(self, item, path, game, key):
        del item
        self._set_cover_by_key(path, game, key)

    def _set_cover_legacy_guard(self, item):
        try:
            return self.list.row(item)
        except RuntimeError:
            return -1
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
            self.recent = self._get_setting("recent_forced_games", []) or []
            self.recent = self.config_manager.get_setting("recent_forced_games", []) or []
        except Exception:
            logger.exception("Failed to reload recent games")
            self.recent = []

        if self._loading:
            return
        if not self._loaded:
            if not self._loading:
                QTimer.singleShot(0, self.initial_load)
            return

        try:
            if self._games_signature() != self._last_games_signature:
                self.load_games()
                self._loaded = True
                self._discord_entries_loaded = False
                if self._load_discord_cache_on_startup:
                    QTimer.singleShot(50, self.load_discord_cache_async)
                QTimer.singleShot(50, self.load_discord_cache_async)
        except Exception:
            logger.exception("Failed to detect/reload changed game map")
        try:
            if self._games_signature() != self._last_games_signature:
                self.load_local_games()
                self._discord_entries_loaded = False
                QTimer.singleShot(50, self.load_discord_cache_async)
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
            ev.ignore()
            self.hide()
            return
        super().closeEvent(ev)

    def _entry_key(self, entry: GameEntry) -> Tuple[str, str, str]:
        return (entry.name.lower().strip(), str(entry.steam_appid or "").strip(), str(entry.id or "").strip())

    def _games_signature(self):
        gm = self.pm.games_map or {}
        return tuple(sorted((k.lower(), str((v or {}).get("client_id") or ""), str((v or {}).get("steam_appid") or "")) for k, v in gm.items()))
