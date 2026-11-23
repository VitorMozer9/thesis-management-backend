import logging
import subprocess
import sys
from io import BytesIO
from unicodedata import normalize


from thesis.application.ports.pdf_extraction import InvalidPdf, PdfFailure


class PypdfTextExtractor:

    def extract(self, content: bytes) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-m", __name__],
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=45,
            )
        except subprocess.TimeoutExpired:
            raise InvalidPdf(PdfFailure.TIME_LIMIT) from None

        if result.returncode == 2:
            raise InvalidPdf(PdfFailure(result.stdout.decode("ascii")))
        if result.returncode:
            raise RuntimeError("O processo de extração foi interrompido.")

        return result.stdout.decode("utf-8")


def read_pages(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content), strict=True)
    if reader.is_encrypted:
        raise InvalidPdf(PdfFailure.ENCRYPTED)
    if len(reader.pages) > 500:
        raise InvalidPdf(PdfFailure.PAGE_LIMIT)

    pages = []
    length = 0
    for page in reader.pages:
        text = normalize("NFC", page.extract_text()).replace("\x00", "").strip()
        if not text:
            continue

        length += len(text) + (2 if pages else 0)
        if length > 1_000_000:
            raise InvalidPdf(PdfFailure.TEXT_LIMIT)
        pages.append(text)

    if not pages:
        raise InvalidPdf(PdfFailure.NO_TEXT)

    return "\n\n".join(pages)


def main() -> int:
    logging.disable(logging.CRITICAL)
    if sys.platform.startswith("linux"):
        import resource

        budget = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (budget, budget))

    try:
        output = read_pages(sys.stdin.buffer.read()).encode("utf-8")
    except InvalidPdf as exc:
        failure = exc.reason
    except MemoryError:
        failure = PdfFailure.TOO_LARGE
    except Exception:
        failure = PdfFailure.CORRUPT
    else:
        sys.stdout.buffer.write(output)
        return 0

    sys.stdout.buffer.write(failure.value.encode("ascii"))
    return 2


if __name__ == "__main__":
    sys.exit(main())
