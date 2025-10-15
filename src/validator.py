"""
Request validation module.

Validates the structure and content of incoming JSON requests
to ensure all required fields are present and properly formatted.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RequestValidator:
    """Validates incoming API requests."""
    
    REQUIRED_FIELDS = ["email", "secret", "task", "round", "nonce", "brief", "evaluation_url"]
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate request data structure.
        
        Args:
            data: The request payload as a dictionary
            
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        logger.debug(f"Validating request data for task: {data.get('task', 'unknown')}")
        
        # Check for required fields
        missing = [field for field in RequestValidator.REQUIRED_FIELDS if field not in data]
        if missing:
            error_msg = f"Missing required fields: {', '.join(missing)}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        # Validate field types
        if not isinstance(data["email"], str) or "@" not in data["email"]:
            return False, "Invalid email format"
        
        if not isinstance(data["task"], str) or not data["task"]:
            return False, "Task must be a non-empty string"
        
        if not isinstance(data["round"], int) or data["round"] < 1:
            return False, "Round must be a positive integer"
        
        if not isinstance(data["nonce"], str) or not data["nonce"]:
            return False, "Nonce must be a non-empty string"
        
        if not isinstance(data["brief"], str) or not data["brief"]:
            return False, "Brief must be a non-empty string"
        
        if not isinstance(data["evaluation_url"], str) or not data["evaluation_url"].startswith("http"):
            return False, "Evaluation URL must be a valid HTTP(S) URL"
        
        # Optional fields validation
        if "checks" in data and not isinstance(data["checks"], list):
            return False, "Checks must be a list"
        
        if "attachments" in data:
            if not isinstance(data["attachments"], list):
                return False, "Attachments must be a list"
            for att in data["attachments"]:
                if not isinstance(att, dict) or "name" not in att or "url" not in att:
                    return False, "Each attachment must have 'name' and 'url'"
        
        logger.debug(f"Validation passed for task: {data['task']}")
        return True, None
