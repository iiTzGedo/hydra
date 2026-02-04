"""NotificationService — composed from focused mixins."""

from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient
from hydra.api.v1.services.notifications.emission import EmissionMixin
from hydra.api.v1.services.notifications.delivery import DeliveryMixin
from hydra.api.v1.services.notifications.query import QueryMixin
from hydra.api.v1.services.notifications.actions import ActionsMixin


class NotificationService(EmissionMixin, DeliveryMixin, QueryMixin, ActionsMixin):
    """Core notification service handling emission, deduplication, and CRUD.

    Design principles:
    - ``emit()`` is fire-and-forget: never raises, logs failures.
    - Read state (``notification_reads``) is per-user; lifecycle state
      (acknowledged, resolved) lives on the notification document.
    - Deduplication uses ``groupKey`` within a configurable time window.
    """

    def __init__(self, mongodb: MongoDB, redis: RedisClient):
        self.db = mongodb
        self.redis = redis
