import json
import mimetypes
from typing import List
from datetime import datetime
from pathlib import Path

from tqdm.asyncio import tqdm_asyncio

from .schemas import ParsedDocument, ParseError


class DocumentParser:
    MIME_PARSERS = {
        "application/pdf": "_parse_pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "_parse_docx",
        "text/html": "_parse_html",
        "text/markdown": "_parse_markdown",
        "text/plain": "_parse_text",
    }

    def __init__(self):
        self.error_log: List[ParseError] = []

    async def parse_file(self, file_path: str) -> ParsedDocument:
        mime_type, _ = mimetypes.guess_type(file_path)

        if mime_type is None:
            mime_type = "text/plain"

        parser_method = self.MIME_PARSERS.get(mime_type, "_parse_text")

        try:
            content = await getattr(self, parser_method)(file_path)
            cleaned = self._clean_content(content)
            metadata = {
                "source": file_path,
                "mime_type": mime_type,
                "parsed_at": datetime.now().isoformat(),
            }
            return ParsedDocument(content=cleaned, metadata=metadata)
        except Exception as e:
            error = ParseError(
                file_path=file_path, error=str(e), timestamp=datetime.now().isoformat()
            )
            self.error_log.append(error)
            self._save_error_log()
            raise

    async def parse_directory(
        self, directory: str, recursive: bool = True
    ) -> List[ParsedDocument]:
        path = Path(directory)
        pattern = "**/*" if recursive else "*"
        files = [str(f) for f in path.glob(pattern) if f.is_file()]

        tasks = [self.parse_file(f) for f in files]
        results = await tqdm_asyncio.gather(*tasks, return_exceptions=True)

        parsed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error = ParseError(
                    file_path=files[i],
                    error=str(result),
                    timestamp=datetime.now().isoformat(),
                )
                self.error_log.append(error)
            else:
                parsed.append(result)

        if self.error_log:
            self._save_error_log()

        return parsed

    async def _parse_pdf(self, file_path: str) -> str:
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n".join(text_parts)
        except ImportError:
            return await self._parse_with_unstructured(file_path)

    async def _parse_docx(self, file_path: str) -> str:
        try:
            from docx import Document

            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
        except ImportError:
            return await self._parse_with_unstructured(file_path)

    async def _parse_html(self, file_path: str) -> str:
        from bs4 import BeautifulSoup

        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator=" ", strip=True)

    async def _parse_markdown(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    async def _parse_text(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    async def _parse_with_unstructured(self, file_path: str) -> str:
        try:
            from unstructured.partition.auto import partition

            elements = partition(filename=file_path)
            return "\n".join([str(el) for el in elements])
        except ImportError:
            return await self._parse_text(file_path)

    def _clean_content(self, content: str) -> str:
        lines = content.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(marker in line for marker in ["---PAGE---", "[PAGE]", "Page \\d+"]):
                continue
            if line.isdigit() and len(line) < 5:
                continue
            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)
        text = "\n".join(line for line in text.split("\n") if line.strip())

        return text

    def _save_error_log(self):
        with open("error_log.json", "w", encoding="utf-8") as f:
            json.dump(
                [e.dict() for e in self.error_log], f, ensure_ascii=False, indent=2
            )
