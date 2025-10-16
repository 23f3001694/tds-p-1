"""
Evaluation notification module.

Handles sending repository metadata to the evaluation server
with exponential backoff retry logic.
"""

import time
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


class EvaluationNotifier:
    """Notifies the evaluation server about completed deployments."""
    
    MAX_RETRIES = 10
    INITIAL_DELAY = 1  # seconds
    
    @staticmethod
    def notify(evaluation_url: str, payload: Dict[str, Any]) -> bool:
        """
        Send notification to evaluation server with retry logic.
        
        Args:
            evaluation_url: The URL to POST the notification to
            payload: Dictionary containing email, task, round, nonce, repo_url, commit_sha, pages_url
            
        Returns:
            True if notification was successful, False otherwise
        """
        headers = {"Content-Type": "application/json"}
        delay = EvaluationNotifier.INITIAL_DELAY
        
        logger.info(f"Starting notification to {evaluation_url}")
        
        for attempt in range(EvaluationNotifier.MAX_RETRIES):
            try:
                logger.debug(f"Notification attempt {attempt + 1}/{EvaluationNotifier.MAX_RETRIES}")
                
                response = httpx.post(
                    evaluation_url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info("Successfully notified evaluation server")
                    return True
                else:
                    logger.warning(f"Server responded with {response.status_code}: {response.text[:200]}")
            
            except Exception as e:
                logger.error(f"Request failed: {e}")
            
            # Don't sleep after the last attempt
            if attempt < EvaluationNotifier.MAX_RETRIES - 1:
                logger.debug(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff: 1, 2, 4, 8, 16 seconds
        
        logger.error("Failed to notify evaluation server after all retries")
        return False
