"""AuthService class combining all auth mixins."""

from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

from .login import LoginMixin
from .tokens import TokensMixin
from .nodes import NodeRegistrationMixin
from .api_keys import ApiKeysMixin
from .agents import AgentRegistrationMixin


class AuthService(
    LoginMixin,
    TokensMixin,
    NodeRegistrationMixin,
    ApiKeysMixin,
    AgentRegistrationMixin,
):
    """Authentication and authorization service."""

    def __init__(self, mongodb: MongoDB, redis: RedisClient | None = None):
        self.db = mongodb
        self.redis = redis
        self.settings = get_settings()
