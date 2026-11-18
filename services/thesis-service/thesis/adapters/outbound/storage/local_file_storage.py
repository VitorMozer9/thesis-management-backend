import shutil

from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from thesis.application.ports.file_storage import FileStoragePort


class LocalFileStorage(FileStoragePort):

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        path = (self.root / key).resolve()

        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key.")

        return path

    def save(
        self,
        key: str,
        content: BinaryIO,
    ) -> str:

        destination = self._resolve_path(key)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_file = destination.with_name(
            f".{destination.name}.{uuid4().hex}.tmp"
        )

        try:
            with temporary_file.open("xb") as output:
                shutil.copyfileobj(
                    content,
                    output,
                    length=1024 * 1024,
                )

            temporary_file.replace(destination)

        finally:
            temporary_file.unlink(missing_ok=True)

        return key

    def delete(self, key: str) -> None:
        path = self._resolve_path(key)
        path.unlink(missing_ok=True)