from celery import shared_task
from app.services.scrapers.pandamaster import PandaMasterScraper
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.worker.tasks.pandamaster_action")
def pandamaster_action(action_type: str, game_name: str = "pandamaster", **kwargs):
    """
    Executes a bot action (balance, deposit, redeem) in a background worker.
    Supports: PandaMaster, FireKirin
    """
    logger.info(f"Starting {game_name} task: {action_type}")
    import asyncio
    
    scraper = None
    if game_name == "pandamaster":
        from app.services.scrapers.pandamaster import PandaMasterScraper
        scraper = PandaMasterScraper()
    elif game_name == "firekirin":
        from app.services.scrapers.firekirin import FireKirinScraper
        scraper = FireKirinScraper()
    elif game_name == "orionstars":
        from app.services.scrapers.orionstars import OrionStarsScraper
        scraper = OrionStarsScraper()
    elif game_name == "milkywayapp":
        from app.services.scrapers.milkyway import MilkyWayScraper
        scraper = MilkyWayScraper()
    else:
        return {"status": "error", "message": f"Unsupported game: {game_name}"}

    try:
        if action_type == "agent_balance":
            # Handle async balance fetch
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            balance, msg = loop.run_until_complete(scraper.get_agent_balance())
            return {"status": "success" if balance is not None else "failure", "balance": balance, "message": msg}
            
        elif action_type == "signup":
            return scraper.player_signup(kwargs.get("fullname"), kwargs.get("requested_username"))
            
        elif action_type == "recharge":
            return scraper.recharge_user(kwargs.get("username"), kwargs.get("amount"))
            
        elif action_type == "redeem":
            return scraper.redeem_user(kwargs.get("username"), kwargs.get("amount"))
            
        else:
            return {"status": "error", "message": f"Unknown action: {action_type}"}
            
    except Exception as e:
        logger.error(f"Task failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if scraper and scraper.driver:
            scraper.close()
