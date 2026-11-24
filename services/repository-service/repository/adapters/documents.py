import hashlib
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from repository.domain import Conflict


class Documents:
    limit = 20 * 1024 * 1024

    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, thesis_id, digest):
        if not isinstance(thesis_id, UUID) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise Conflict("Referência de documento inválida.")
        path = self.root / str(thesis_id) / digest
        if path.resolve() != path:
            raise OSError("Referência de armazenamento inválida.")
        return path

    def receive(self, thesis_id, upload, expected):
        if not 0 < upload.size <= self.limit:
            raise Conflict("O PDF deve ter até 20 MiB.")
        target = self.path(thesis_id, expected)
        directory = target.parent
        directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=directory, delete=False) as output:
                temporary = Path(output.name)
                digest = hashlib.sha256()
                size = 0
                tail = b""
                for chunk in upload.chunks():
                    if size == 0 and not chunk.startswith(b"%PDF-"):
                        raise Conflict("Cabeçalho PDF inválido.")
                    size += len(chunk)
                    if size > self.limit:
                        raise Conflict("PDF excede 20 MiB.")
                    digest.update(chunk)
                    output.write(chunk)
                    tail = (tail + chunk)[-1024:]
                if not tail.rstrip().endswith(b"%%EOF") or digest.hexdigest() != expected:
                    raise Conflict("PDF incompleto ou SHA-256 divergente.")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            if os.name == "posix":
                descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def verified(self, thesis_id, digest):
        stream = self.path(thesis_id, digest).open("rb")
        try:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise OSError("Integridade do documento comprometida.")
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise
