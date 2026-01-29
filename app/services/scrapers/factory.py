import importlib
import logging
from typing import Type
from app.services.scrapers.base import BaseGameScraper

logger = logging.getLogger(__name__)

class ScraperFactory:
    """
    Factory class to dynamically load and instantiate game scrapers.
    """
    
    # Map game names to their module and class names
    # Key: game_name (lowercase), Value: (module_path, class_name)
    SCRAPER_MAP = {
        "pandamaster": ("app.services.scrapers.pandamaster", "PandaMasterScraper"),
        "firekirin": ("app.services.scrapers.firekirin", "FireKirinScraper"),
        "orionstars": ("app.services.scrapers.orionstars", "OrionStarsScraper"),
        "milkywayapp": ("app.services.scrapers.milkyway", "MilkyWayScraper"),
        "juwa777": ("app.services.scrapers.juwa777", "Juwa777Scraper"),
        "vegasx": ("app.services.scrapers.vegasx", "VegasXScraper"),
        "vblink777": ("app.services.scrapers.vblink777", "VBlink777Scraper"),
        "gamevault999": ("app.services.scrapers.gamevault999", "GameVault999Scraper"),
        "ultrapanda": ("app.services.scrapers.ultrapanda", "UltraPandaScraper"),
        "cashfrenzy777": ("app.services.scrapers.cashfrenzy777", "CashFrenzy777Scraper"),
        "cashmachine777": ("app.services.scrapers.cashmachine777", "CashMachine777Scraper"),
        "lasvegassweeps": ("app.services.scrapers.lasvegassweeps", "LasVegasSweepsScraper"),
        "egame99": ("app.services.scrapers.egame99", "EGame99Scraper"),
        "gameroom777": ("app.services.scrapers.gameroom777", "GameRoom777Scraper"),
        "juwa2": ("app.services.scrapers.juwa2", "Juwa2Scraper"),
        "moolah": ("app.services.scrapers.moolah", "MoolahScraper"),
        "mrallinone777": ("app.services.scrapers.mrallinone777", "MrAllInOne777Scraper"),
        "vegasroll": ("app.services.scrapers.vegasroll", "VegasRollScraper"),
    }

    @classmethod
    def get_scraper_class(cls, game_name: str) -> Type[BaseGameScraper]:
        """
        Dynamically import and return the scraper class for a given game.
        """
        game_key = game_name.lower()
        if game_key not in cls.SCRAPER_MAP:
            raise ValueError(f"Unsupported game: {game_name}")

        module_path, class_name = cls.SCRAPER_MAP[game_key]
        
        try:
            module = importlib.import_module(module_path)
            scraper_class = getattr(module, class_name)
            return scraper_class
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Class {class_name} not found in {module_path}: {e}")
            raise

    @classmethod
    def create_scraper(cls, game_name: str) -> BaseGameScraper:
        """
        Instantiate a scraper for the given game.
        """
        scraper_class = cls.get_scraper_class(game_name)
        return scraper_class()
