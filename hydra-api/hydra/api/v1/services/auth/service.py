"""AuthService class combining all auth mixins."""

from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

from .agents import AgentRegistrationMixin
from .api_keys import ApiKeysMixin
from .login import LoginMixin
from .nodes import NodeRegistrationMixin
from .tokens import TokensMixin


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
