import logging
import os
from pathlib import Path
from typing import Dict, Optional
from src.core.utils import safe_json_load, save_json, CONFIG_DIR
from src.core.utils import get_lang_from_registry, load_locale

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('DISCORD_PRESENCE_LANG', 'en')
    TEXTS = load_locale(LANG)


logger = logging.getLogger('discord_presence_manager')

class ConfigManager:
    def __init__(self, config_path_file: Path):
        self.config_path_file = Path(config_path_file)
        self.games_config: Dict = {}
        self.games_config_path: Optional[Path] = None
        self.app_settings: Dict = {
            "start_with_windows": False,
                        "start_discord_on_launch": False,
            "get_cookie_on_launch": False,
            "idle_presence_enabled": False,
            "clear_presence_when_idle": True,
            "open_game_picker_on_startup": True,
            "minimize_to_tray_on_close": True,
            "remember_window_size": True,
            "show_recent_games_first": True,
            "enable_game_art_download": True,
            "steamgriddb_api_key": "",
            "game_art_cache_days": 30,
            "recent_forced_games": [],
            "game_picker_max_visible_results": 120,
            "game_picker_search_limit": 50,
            "game_picker_empty_limit": 24,
            "game_art_initial_batch_size": 4,
            "game_art_batch_size": 2,
            "load_discord_cache_on_startup": False
        }
        self.app_settings_path = CONFIG_DIR / "app_settings.json"
        self._load()

    def _load(self):
        # Ruta fija al archivo que siempre queremos cargar
        fixed_path = CONFIG_DIR / "games_config_merged.json"
        
        # Cargar app_settings.json
        if self.app_settings_path.exists():
            data_settings = safe_json_load(self.app_settings_path)
            if isinstance(data_settings, dict):
                # Update defaults with loaded settings
                missing_before = set(self.app_settings.keys()) - set(data_settings.keys())
                self.app_settings.update(data_settings)
                if missing_before:
                    save_json(self.app_settings, self.app_settings_path)
        else:
            save_json(self.app_settings, self.app_settings_path)

        # Si no existe, mostrar error en logs pero NO abrir Tkinter
        if not fixed_path.exists():
            logger.error(f"❌ No se encontró {fixed_path}. Se cargará un JSON vacío.")
            self.games_config = {}
            self.games_config_path = fixed_path
            return

        # Cargar JSON fijo directamente sin pedir nada al usuario
        data = safe_json_load(fixed_path)
        if isinstance(data, dict):
            self.games_config = data
            self.games_config_path = fixed_path
            logger.info(TEXTS.get("games_config_merged", "✅ games_config_merged.json cargado automáticamente: {fixed_path}").format(fixed_path=fixed_path))
            self._log_games_summary()
        else:
            logger.warning(TEXTS.get("games_config_invalid", "⚠️ games_config_merged.json no contiene un objeto JSON válido."))
            self.games_config = {}
            self.games_config_path = fixed_path

    def _log_games_summary(self, verbose=False):
        count = len(self.games_config)
        if count == 0:
            logger.warning(TEXTS.get("no_games_found", "⚠️ No se encontraron juegos en la configuración."))
            return
        
        logger.info(TEXTS.get("games_loaded", "📦 Juegos cargados: {count}").format(count=count))

    def get_game_mapping(self):
        return self.games_config

    def get_setting(self, key: str, default=None):
        return self.app_settings.get(key, default)

    def set_setting(self, key: str, value):
        self.app_settings[key] = value
        save_json(self.app_settings, self.app_settings_path)
