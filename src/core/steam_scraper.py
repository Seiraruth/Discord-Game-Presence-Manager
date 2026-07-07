import requests
import logging
import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger('discord_presence_manager')

class SteamScraper: 
    def __init__(self, steam_cookie: Optional[str], test_rich_url: str):
        self.test_rich_url = test_rich_url
        self.session = requests.Session()
        if steam_cookie:
            self.session.cookies.set('steamLoginSecure', steam_cookie, domain='steamcommunity.com')
        
        # Basic headers to appear as a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self._last_presence = None
        self._last_group_size = None
        
    def set_cookie(self, steam_cookie: str):
        if steam_cookie:
            self.session.cookies.set('steamLoginSecure', steam_cookie, domain='steamcommunity.com')
            self._steam_expired_warned = False
            logger.info("🍪 Steam cookie updated in Scraper.")


    def get_rich_presence(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Returns a tuple (rich_presence_text, group_size)
        """
        if not self.test_rich_url:
            logger.debug("No TEST_RICH_URL configured.")
            return None, None
        
        try:
            resp = self.session.get(self.test_rich_url, timeout=10)
            if resp.status_code != 200:
                logger.debug("Status != 200 when getting rich presence")
                return None, None
            
            if "Sign In" in resp.text or "login" in resp.url.lower():
                if not getattr(self, "_steam_expired_warned", False):
                    logger.warning("🔒 Steam session expired.")
                    self._steam_expired_warned = True
                return None, None
            else:
                if getattr(self, "_steam_expired_warned", False):
                    logger.info("✅ Steam session restored.")
                    self._steam_expired_warned = False

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Get Rich Presence text
            # Try first with "Localized Rich Presence Result"
            rich_presence_text = None
            b = soup.find('b', string=re.compile(r'Localized Rich Presence Result', re.IGNORECASE))
            if b:
                text = (b.next_sibling or "").strip()
                if text and '#' not in text and "No rich presence keys set" not in text:
                    rich_presence_text = text

            # If it fails, try searching for "status" in the table (more robust fallback)
            if not rich_presence_text:
                rows = soup.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text().strip().lower()
                        if key == 'status':
                            val = cells[1].get_text().strip()
                            if val and '#' not in val:
                                rich_presence_text = val
                                logger.debug(f"✅ Rich Presence found via fallback 'status': {val}")
                                break

            if rich_presence_text:
                if rich_presence_text != self._last_presence:
                    self._last_presence = rich_presence_text
                    logger.info(f"🎮 Rich Presence (nuevo): {rich_presence_text}")
            else:
                 # If null after both attempts, log if changed (to avoid flooding)
                 pass
            
            # 2. Extraer steam_player_group_size
            group_size = self._extract_group_size(soup)
            
            return rich_presence_text, group_size
            
        except Exception as e:
            logger.error(f"⚠️ Error scraping Steam: {e}")
            return None, None
    
    def _extract_group_size(self, soup) -> Optional[int]:
        """
        Extracts the steam_player_group_size value from the HTML table
        """
        group_size = None
        try:
            # Search for the row containing 'steam_player_group_size'
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    first_cell_text = cells[0].get_text().strip()
                    if 'steam_player_group_size' in first_cell_text:
                        # The value is in the second cell
                        group_size_text = cells[1].get_text().strip()
                        if group_size_text.isdigit():
                            group_size = int(group_size_text)
                            if group_size != self._last_group_size:
                                self._last_group_size = group_size
                                logger.info(f"👥 Group size detected: {group_size}")
                            return group_size
            
            # If steam_player_group_size not found, search for alternative patterns
            #group_size = self._find_alternative_group_size(soup)
            return group_size
            
        except Exception as e:
            logger.debug(f"Error extracting group size: {e}")
            return None
    
    def _find_alternative_group_size(self, soup) -> Optional[int]:
        """
        Searches for group size using alternative methods (XPath simulation)
        """
        try:
            # Method 1: Search all cells that may contain group numbers
            cells = soup.find_all('td')
            for cell in cells:
                text = cell.get_text().strip()
                # Search for patterns like "1/4", "2 players", etc.
                if '/' in text and text.replace('/', '').isdigit():
                    parts = text.split('/')
                    if len(parts) == 2 and parts[0].isdigit():
                        current_players = int(parts[0])
                        logger.info(f"👥 Alternative group size detected: {current_players}")
                        return current_players
            
            # Method 2: Search for numbers representing player count
            for cell in cells:
                text = cell.get_text().strip()
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= 16:  # Reasonable range for game groups
                        logger.info(f"👥 Numeric group size detected: {num}")
                        return num
            
            return None
        except Exception as e:
            logger.debug(f"Error in alternative group size search: {e}")
            return None
            
def find_steam_appid_by_name(game_name: str) -> Optional[str]:
    try:
        url = f"https://steamcommunity.com/actions/SearchApps/{game_name}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list):
                for app in data:
                    if app.get("name", "").lower() == game_name.lower():
                        return str(app.get("appid"))
                if data:    
                    return str(data[0].get("appid"))
    except Exception as e:
        logger.error(f"Error searching Steam AppID: {e}")
    return None
