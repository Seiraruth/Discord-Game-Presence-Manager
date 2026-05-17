import os
import psutil
import subprocess
import logging
import json
import time
from pathlib import Path
from typing import Optional
from src.core.utils import get_lang_from_registry, load_locale

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('DISCORD_PRESENCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('discord_presence_manager')

class AppLauncher:
    @staticmethod
    def find_discord() -> Optional[str]:
        p = Path(os.getenv("LOCALAPPDATA", "")) / "Discord" / "Update.exe"
        if p.exists():
            return str(p)
        return None

    @staticmethod
    def launch_discord():
        for proc in psutil.process_iter(attrs=['name']):
            name = (proc.info.get('name') or "").lower()
            if "discord" in name and "update" not in name:
                logger.info(TEXTS.get("already_running_discord", "💡 Discord ya está en ejecución"))
                return
        updater = AppLauncher.find_discord()
        if updater:
            logger.info(TEXTS.get("launching_discord", "🚀 Iniciando Discord..."))
            subprocess.Popen([updater, "--processStart", "Discord.exe"])
        else:
            logger.warning("⚠️ No se encontró Discord instalado en la ruta por defecto.")
