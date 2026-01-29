from celery import shared_task
from app.services.scrapers.pandamaster import PandaMasterScraper
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.worker.tasks.pandamaster_action")
def pandamaster_action(action_type: str, **kwargs):
    """
    Executes a PandaMaster action (balance, deposit, redeem) in a background worker.
    """
    logger.info(f"Starting PandaMaster task: {action_type}")
    scraper = PandaMasterScraper()
    
    try:
        # 1. Login
        if not scraper.login():
            return {"status": "error", "message": "Login failed"}
        
        # 2. Perform Action
        result = None
        if action_type == "agent_balance":
            result = scraper.get_agent_balance()
        # Add other actions here
            
        return {"status": "success", "data": result}
        
    except Exception as e:
        logger.error(f"Task failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        scraper.close()
