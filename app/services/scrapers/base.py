from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, Union

class BaseGameScraper(ABC):
    """
    Abstract base class for all game scrapers.
    Enforces a standard interface for bot actions.
    """
    
    def __init__(self, username: str = None, password: str = None):
        self.username = username
        self.password = password
        self.driver = None

    @abstractmethod
    def close(self):
        """Close the browser instance."""
        pass

    @abstractmethod
    async def get_agent_balance(self) -> Tuple[Optional[float], str]:
        """
        Get the agent's current balance.
        Returns: (balance, message)
        """
        pass

    @abstractmethod
    def player_signup(self, fullname: str, requested_username: str = None) -> Dict[str, Any]:
        """
        Create a new player account.
        Returns: Dictionary with status and details.
        """
        pass

    @abstractmethod
    def recharge_user(self, username: str, amount: float) -> Dict[str, Any]:
        """
        Deposit credits to a user.
        Returns: Dictionary with status and transaction details.
        """
        pass

    @abstractmethod
    def redeem_user(self, username: str, amount: float) -> Dict[str, Any]:
        """
        Withdraw credits from a user.
        Returns: Dictionary with status and transaction details.
        """
        pass
