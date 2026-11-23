from typing import Protocol
from uuid import UUID


class RateLimitExceeded(Exception):

    def __init__(self, retry_after: int):
        super().__init__("Limite de requisições excedido.")
        self.retry_after = retry_after


class RateLimitPort(Protocol):

    def consume(self, account_id: UUID) -> None:
        ...
