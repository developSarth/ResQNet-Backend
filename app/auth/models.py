# Auth models - Use models from models.db_models
# This file kept for backward compatibility

# Re-export User from the main db_models
from models.db_models import User

__all__ = ["User"]