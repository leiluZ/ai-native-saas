import pytest
import tempfile
import os
from pathlib import Path
from src.rag.document_parser import DocumentParser


class TestDocumentParserSingleFile:
    """单文件解析测试"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "documents"

    @pytest.mark.asyncio
    async def test_parse_utf8_txt(self, parser, fixtures_dir):
        """测试UTF-8编码的TXT文件"""
        file_path = str(fixtures_dir / "test_utf8.txt")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert len(result.content) > 0
        assert "UTF-8" in result.content
        assert result.metadata["mime_type"] == "text/plain"
        assert "source" in result.metadata

    @pytest.mark.asyncio
    async def test_parse_gbk_txt(self, parser, fixtures_dir):
        """测试GBK编码的TXT文件"""
        file_path = str(fixtures_dir / "test_gbk.txt")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert len(result.content) > 0
        assert "GBK" in result.content
        assert result.metadata["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_parse_empty_txt(self, parser, fixtures_dir):
        """测试空TXT文件"""
        file_path = str(fixtures_dir / "test_empty.txt")
        result = await parser.parse_file(file_path)

        assert result.content == ""
        assert result.metadata["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_parse_html(self, parser, fixtures_dir):
        """测试HTML文件"""
        file_path = str(fixtures_dir / "test.html")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert len(result.content) > 0
        assert "HTML" in result.content
        assert result.metadata["mime_type"] == "text/html"

    @pytest.mark.asyncio
    async def test_parse_markdown(self, parser, fixtures_dir):
        """测试Markdown文件"""
        file_path = str(fixtures_dir / "test.md")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert len(result.content) > 0
        assert "Markdown" in result.content
        assert result.metadata["mime_type"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_parse_pdf(self, parser, fixtures_dir):
        """测试PDF文件"""
        file_path = str(fixtures_dir / "test.pdf")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert result.metadata["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_parse_docx(self, parser, fixtures_dir):
        """测试DOCX文件"""
        file_path = str(fixtures_dir / "test.docx")
        result = await parser.parse_file(file_path)

        assert result.content is not None
        assert len(result.content) > 0
        assert "DOCX" in result.content
        assert result.metadata["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class TestDocumentParserMultipleFiles:
    """多文件解析测试"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "documents"

    @pytest.mark.asyncio
    async def test_parse_multiple_files(self, parser, fixtures_dir):
        """测试解析多个文件"""
        file_paths = [
            str(fixtures_dir / "test_utf8.txt"),
            str(fixtures_dir / "test.html"),
            str(fixtures_dir / "test.md"),
        ]

        result = await parser.parse_files(file_paths)

        assert len(result["success"]) == 3
        assert len(result["errors"]) == 0

        # 验证每个文件的解析结果
        contents = [doc["content"] for doc in result["success"]]
        assert any("UTF-8" in content for content in contents)
        assert any("HTML" in content for content in contents)
        assert any("Markdown" in content for content in contents)

    @pytest.mark.asyncio
    async def test_parse_mixed_valid_invalid(self, parser, fixtures_dir):
        """测试混合有效和无效文件"""
        # 创建一个不存在的文件路径
        nonexistent_file = str(fixtures_dir / "nonexistent.txt")

        file_paths = [
            str(fixtures_dir / "test_utf8.txt"),
            nonexistent_file,
        ]

        result = await parser.parse_files(file_paths)

        assert len(result["success"]) == 1
        assert len(result["errors"]) == 1
        assert "UTF-8" in result["success"][0]["content"]

    @pytest.mark.asyncio
    async def test_parse_all_formats(self, parser, fixtures_dir):
        """测试解析所有格式的文件"""
        file_paths = [
            str(fixtures_dir / "test_utf8.txt"),
            str(fixtures_dir / "test_gbk.txt"),
            str(fixtures_dir / "test.html"),
            str(fixtures_dir / "test.md"),
            str(fixtures_dir / "test.pdf"),
            str(fixtures_dir / "test.docx"),
        ]

        result = await parser.parse_files(file_paths)

        assert len(result["success"]) == 6
        assert len(result["errors"]) == 0

        # 验证所有格式都被正确解析
        mime_types = [doc["metadata"]["mime_type"] for doc in result["success"]]
        assert "text/plain" in mime_types
        assert "text/html" in mime_types
        assert "text/markdown" in mime_types
        assert "application/pdf" in mime_types
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in mime_types


class TestDocumentParserEdgeCases:
    """边界条件测试"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.mark.asyncio
    async def test_parse_nonexistent_file(self, parser):
        """测试解析不存在的文件"""
        with pytest.raises(Exception):
            await parser.parse_file("/path/to/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_parse_binary_file_as_text(self, parser, tmp_path):
        """测试将二进制文件作为文本解析"""
        # 创建一个包含无效UTF-8字节的文件
        binary_file = tmp_path / "binary.txt"
        binary_file.write_bytes(b"\x80\x81\x82\x83")

        # 应该能够解析（使用latin-1编码回退）
        result = await parser.parse_file(str(binary_file))
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_parse_large_file(self, parser, tmp_path):
        """测试解析大文件"""
        large_file = tmp_path / "large.txt"
        large_content = "这是一个测试行。\n" * 1000
        large_file.write_text(large_content, encoding="utf-8")

        result = await parser.parse_file(str(large_file))
        assert result.content is not None
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_parse_file_with_special_chars(self, parser, tmp_path):
        """测试解析包含特殊字符的文件"""
        special_file = tmp_path / "special.txt"
        special_content = "特殊字符：αβγδε\nEmoji：🎉🌟💻\n数学：∑∏∫\n"
        special_file.write_text(special_content, encoding="utf-8")

        result = await parser.parse_file(str(special_file))
        assert result.content is not None
        assert "αβγδε" in result.content

    @pytest.mark.asyncio
    async def test_parse_empty_files_list(self, parser):
        """测试解析空文件列表"""
        result = await parser.parse_files([])
        assert len(result["success"]) == 0
        assert len(result["errors"]) == 0


class TestDocumentParserDirectory:
    """目录解析测试"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures" / "documents"

    @pytest.mark.asyncio
    async def test_parse_directory(self, parser, fixtures_dir):
        """测试解析目录中的所有文件"""
        result = await parser.parse_directory(str(fixtures_dir))

        # 应该解析所有测试文件
        assert len(result) >= 6

        # 验证不同格式的文件都被解析
        contents = [doc.content for doc in result]
        assert any("UTF-8" in content for content in contents)
        assert any("HTML" in content for content in contents)

    @pytest.mark.asyncio
    async def test_parse_directory_recursive(self, parser, tmp_path):
        """测试递归解析目录"""
        # 创建嵌套目录结构
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "file1.txt").write_text("文件1内容", encoding="utf-8")
        (subdir / "file2.txt").write_text("文件2内容", encoding="utf-8")

        result = await parser.parse_directory(str(tmp_path))

        assert len(result) == 2
        contents = [doc.content for doc in result]
        assert any("文件1" in content for content in contents)
        assert any("文件2" in content for content in contents)


class TestDocumentParserEncodingDetection:
    """编码检测测试"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.mark.asyncio
    async def test_utf8_bom(self, parser, tmp_path):
        """测试UTF-8 BOM文件"""
        bom_file = tmp_path / "bom.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfUTF-8 BOM\xe5\x86\x85\xe5\xae\xb9")

        result = await parser.parse_file(str(bom_file))
        assert "UTF-8 BOM" in result.content

    @pytest.mark.asyncio
    async def test_latin1_encoding(self, parser, tmp_path):
        """测试Latin-1编码文件"""
        latin_file = tmp_path / "latin.txt"
        latin_file.write_bytes(b"Caf\xe9 r\xe9sum\xe9")  # Café résumé in latin-1

        result = await parser.parse_file(str(latin_file))
        assert "Caf" in result.content

    @pytest.mark.asyncio
    async def test_mixed_encoding_content(self, parser, tmp_path):
        """测试混合编码内容"""
        mixed_file = tmp_path / "mixed.txt"
        # UTF-8编码的中文
        mixed_file.write_text("中文内容\nEnglish content\n123", encoding="utf-8")

        result = await parser.parse_file(str(mixed_file))
        assert "中文" in result.content
        assert "English" in result.content
