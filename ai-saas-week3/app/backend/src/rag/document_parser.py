import asyncio
import json
import mimetypes
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from tqdm.asyncio import tqdm_asyncio

from .schemas import ParsedDocument, ParseError


class DocumentParser:
    def __init__(self):
        self.parsers = {
            'application/pdf': self._parse_pdf,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': self._parse_docx,
            'text/html': self._parse_html,
            'text/markdown': self._parse_markdown,
            'text/plain': self._parse_text,
        }

    async def parse_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """批量解析文件"""
        results = {
            'success': [],
            'errors': []
        }

        tasks = [self._parse_file(path) for path in file_paths]
        parsed_results = await tqdm_asyncio.gather(*tasks, desc="解析文档")

        for result in parsed_results:
            if isinstance(result, ParsedDocument):
                results['success'].append(result.dict())
            elif isinstance(result, ParseError):
                results['errors'].append(result.dict())

        if results['errors']:
            self._write_error_log(results['errors'])

        return results

    async def _parse_file(self, file_path: str) -> ParsedDocument | ParseError:
        """解析单个文件"""
        try:
            mime_type = self._get_mime_type(file_path)
            parser = self.parsers.get(mime_type)

            if not parser:
                raise ValueError(f"不支持的文件类型: {mime_type}")

            content, metadata = await parser(file_path)
            cleaned_content = self._clean_content(content)

            return ParsedDocument(
                content=cleaned_content,
                metadata={
                    **metadata,
                    'source': file_path,
                    'mime_type': mime_type,
                    'parsed_at': datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ParseError(
                file_path=file_path,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat()
            )

    def _get_mime_type(self, file_path: str) -> str:
        """获取文件 MIME 类型"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'

    async def _parse_pdf(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        """解析 PDF 文件"""
        try:
            from pypdf import PdfReader

            loop = asyncio.get_event_loop()
            reader = await loop.run_in_executor(None, PdfReader, file_path)

            content = ""
            metadata = {'page_count': len(reader.pages)}

            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                content += f"\n--- Page {page_num} ---\n{page_text}"

            return content.strip(), metadata
        except ImportError:
            raise ImportError("需要安装 pypdf: pip install pypdf")

    async def _parse_docx(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        """解析 DOCX 文件"""
        try:
            from docx import Document

            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, Document, file_path)

            content = "\n".join([para.text for para in doc.paragraphs])
            metadata = {'paragraph_count': len(doc.paragraphs)}

            return content, metadata
        except ImportError:
            raise ImportError("需要安装 python-docx: pip install python-docx")

    async def _parse_html(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        """解析 HTML 文件"""
        try:
            from bs4 import BeautifulSoup

            loop = asyncio.get_event_loop()

            with open(file_path, 'r', encoding='utf-8') as f:
                soup = await loop.run_in_executor(None, BeautifulSoup, f.read(), 'html.parser')

            content = soup.get_text(separator='\n', strip=True)
            metadata = {'title': soup.title.string if soup.title else ""}

            return content, metadata
        except ImportError:
            raise ImportError("需要安装 beautifulsoup4: pip install beautifulsoup4")

    async def _parse_markdown(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        """解析 Markdown 文件"""
        loop = asyncio.get_event_loop()

        def read_file():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        content = await loop.run_in_executor(None, read_file)
        return content, {}

    async def _parse_text(self, file_path: str) -> tuple[str, Dict[str, Any]]:
        """解析纯文本文件"""
        loop = asyncio.get_event_loop()

        def read_file():
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()

        content = await loop.run_in_executor(None, read_file)
        return content, {}

    def _clean_content(self, content: str) -> str:
        """清洗文档内容"""
        import re

        # 去除多余空白
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        content = re.sub(r'\t+', ' ', content)

        # 去除页码和水印占位符
        content = re.sub(r'^\s*\d+\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'-\d+-', '', content)
        content = re.sub(r'Page\s+\d+\s+of\s+\d+', '', content, flags=re.IGNORECASE)

        # 去除页眉页脚常见模式
        content = re.sub(r'^\s*[\u4e00-\u9fa5a-zA-Z0-9_]{1,10}\s*$', '', content, flags=re.MULTILINE)

        # 统一 Unicode 编码
        content = content.encode('unicode_escape').decode('unicode_escape')

        return content.strip()

    def _write_error_log(self, errors: List[Dict[str, Any]]) -> None:
        """写入错误日志"""
        log_dir = Path('error_logs')
        log_dir.mkdir(exist_ok=True)

        log_path = log_dir / f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
