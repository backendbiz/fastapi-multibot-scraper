from celery import shared_task
from app.services.scrapers.pandamaster import PandaMasterScraper
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.worker.tasks.pandamaster_action")
def pandamaster_action(action_type: str, game_name: str = "pandamaster", **kwargs):
    """
    Executes a bot action (balance, deposit, redeem) in a background worker.
    Supports all games registered in ScraperFactory.
    """
    logger.info(f"Starting {game_name} task: {action_type}")
    import asyncio
    from app.services.scrapers.factory import ScraperFactory
    
    scraper = None
    try:
        # Use factory to get the correct scraper
        try:
            scraper = ScraperFactory.create_scraper(game_name)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Failed to instantiate scraper for {game_name}: {e}")
            return {"status": "error", "message": f"System error loading bot: {str(e)}"}

        # Helper to run async methods synchronously
        def run_async(coro):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)

        if action_type == "agent_balance":
            # Handle async balance fetch
            balance, msg = run_async(scraper.get_agent_balance())
            return {"status": "success" if balance is not None else "failure", "balance": balance, "message": msg}
            
        elif action_type == "signup":
            # Note: Signup might be sync or async depending on implementation
            # Check if method is coroutine
            if asyncio.iscoroutinefunction(scraper.player_signup):
                return run_async(scraper.player_signup(kwargs.get("fullname"), kwargs.get("requested_username")))
            else:
                return scraper.player_signup(kwargs.get("fullname"), kwargs.get("requested_username"))
            
        elif action_type == "recharge":
            if asyncio.iscoroutinefunction(scraper.recharge_user):
                return run_async(scraper.recharge_user(kwargs.get("username"), kwargs.get("amount")))
            else:
                return scraper.recharge_user(kwargs.get("username"), kwargs.get("amount"))
            
        elif action_type == "redeem":
            if asyncio.iscoroutinefunction(scraper.redeem_user):
                 return run_async(scraper.redeem_user(kwargs.get("username"), kwargs.get("amount")))
            else:
                return scraper.redeem_user(kwargs.get("username"), kwargs.get("amount"))
            
        else:
            return {"status": "error", "message": f"Unknown action: {action_type}"}
            
    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        if scraper and hasattr(scraper, 'close'):
            try:
                scraper.close()
            except Exception as e:
                logger.error(f"Error closing scraper: {e}")
