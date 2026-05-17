import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.core.utils import CONFIG_DIR

class GameArtResolver:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.cache_days = int(config_manager.get_setting("game_art_cache_days", 30) or 30)
        self.enabled = bool(config_manager.get_setting("enable_game_art_download", True))
        self.cache_dir = CONFIG_DIR / "cache" / "game_art"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = CONFIG_DIR / "cache" / "game_art_index.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict:
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")

    def _key(self, game: Dict) -> str:
        name = (game.get("name") or "unknown").strip().lower()
        sid = str(game.get("steam_appid") or "")
        cid = str(game.get("id") or game.get("client_id") or "")
        raw = f"{name}|{sid}|{cid}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get_cached_path(self, game: Dict) -> Optional[Path]:
        key = self._key(game)
        meta = self._index.get(key)
        if not meta:
            return None
        p = Path(meta.get("path", ""))
        if not p.exists():
            return None
        if time.time() - meta.get("ts", 0) > self.cache_days * 86400:
            return None
        return p

    def resolve(self, game: Dict) -> Optional[Path]:
        cached = self.get_cached_path(game)
        if cached:
            return cached
        if not self.enabled:
            return None
        for url in self._candidate_urls(game):
            p = self._download(url, self._key(game))
            if p:
                return p
        return None

    def _candidate_urls(self, game: Dict):
        appid = game.get("steam_appid")
        if appid:
            appid = str(appid)
            yield f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"
            yield f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
            yield f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900.jpg"

        key = self.config_manager.get_setting("steamgriddb_api_key") or os.getenv("STEAMGRIDDB_API_KEY", "").strip()
        if key and game.get("name"):
            name = quote(game["name"])
            yield ("sgdb://" + name)

    def _download(self, url: str, cache_key: str) -> Optional[Path]:
        if url.startswith("sgdb://"):
            return self._download_from_sgdb(url[len("sgdb://"):], cache_key)
        try:
            req = Request(url, headers={"User-Agent": "DiscordPresenceManager/1.0"})
            with urlopen(req, timeout=8) as r:
                data = r.read()
                if not data:
                    return None
                ext = ".jpg"
                out = self.cache_dir / f"{cache_key}{ext}"
                out.write_bytes(data)
                self._index[cache_key] = {"path": str(out), "ts": time.time(), "url": url}
                self._save_index()
                return out
        except Exception:
            return None

    def _download_from_sgdb(self, query: str, cache_key: str) -> Optional[Path]:
        key = self.config_manager.get_setting("steamgriddb_api_key") or os.getenv("STEAMGRIDDB_API_KEY", "").strip()
        if not key:
            return None
        try:
            search = Request(
                f"https://www.steamgriddb.com/api/v2/search/autocomplete/{query}",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urlopen(search, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            items = data.get("data") or []
            if not items:
                return None
            game_id = items[0].get("id")
            if not game_id:
                return None
            grids_req = Request(
                f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urlopen(grids_req, timeout=8) as r:
                grids = json.loads(r.read().decode("utf-8"))
            gdata = grids.get("data") or []
            if not gdata:
                return None
            return self._download(gdata[0].get("url", ""), cache_key)
        except Exception:
            return None
