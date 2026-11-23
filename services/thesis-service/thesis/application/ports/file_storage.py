from typing import Protocol, BinaryIO

class FileStoragePort(Protocol):

    def save(
        self,
        key: str,
        content: BinaryIO,
    ) -> str:
        ...

    def delete(self, key: str) -> None:
        ...

    def open(self, key: str) -> BinaryIO:
        ...
