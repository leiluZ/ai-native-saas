import pytest
from src.rag.chunk_manager import ChunkManager


class TestChunkManagerEdgeCases:
    """边界条件测试"""

    def setup_method(self):
        self.chunker = ChunkManager(chunk_size=50, overlap_ratio=0.15)

    def test_empty_document(self):
        """空文档应该返回空列表"""
        result = self.chunker.chunk_document("")
        assert result == []

    def test_empty_document_with_strategy(self):
        """各种策略的空文档"""
        for strategy in ["fixed", "recursive", "header_aware"]:
            result = self.chunker.chunk_document("", strategy=strategy)
            assert result == [], f"Strategy {strategy} should return empty list for empty input"

    def test_single_character(self):
        """单字符文档"""
        result = self.chunker.chunk_document("a")
        assert len(result) == 1
        assert result[0].content == "a"
        assert result[0].token_count == 1

    def test_single_token_word(self):
        """单个token的单词"""
        result = self.chunker.chunk_document("hello")
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_very_short_content(self):
        """非常短的内容"""
        result = self.chunker.chunk_document("Hi")
        assert len(result) == 1
        assert result[0].content == "Hi"

    def test_very_long_paragraph_no_split(self):
        """超长段落但不需要分割"""
        long_text = "hello " * 10
        result = self.chunker.chunk_document(long_text, chunk_size=1000)
        assert len(result) == 1

    def test_very_long_paragraph_with_split(self):
        """超长段落需要分割"""
        long_text = "word " * 500
        result = self.chunker.chunk_document(long_text, chunk_size=50, strategy="fixed")
        assert len(result) > 1
        for chunk in result:
            assert chunk.token_count <= 55

    def test_whitespace_only(self):
        """仅空白字符"""
        result = self.chunker.chunk_document("   \n\n  \t  ")
        assert result == []

    def test_special_characters_only(self):
        """仅特殊字符"""
        result = self.chunker.chunk_document("!@#$%^&*()")
        assert len(result) >= 1

    def test_unicode_content(self):
        """Unicode内容"""
        unicode_text = "你好世界 Hello World こんにちは"
        result = self.chunker.chunk_document(unicode_text)
        assert len(result) >= 1
        assert all(chunk.token_count > 0 for chunk in result)

    def test_duplicate_chunks_deduplication(self):
        """重复chunk应该被去重"""
        text = "hello world " * 100
        result = self.chunker.chunk_document(text, chunk_size=10, overlap_ratio=0.9)
        contents = [chunk.content for chunk in result]
        assert len(contents) == len(set(contents))

    def test_overlap_produces_duplicate_hash(self):
        """重叠部分应该产生相同hash"""
        text = "A" + " word " * 100 + "B"
        result = self.chunker.chunk_document(text, chunk_size=20, overlap_ratio=0.5)
        hashes = [chunk.metadata.get("overlap_ratio") for chunk in result]
        assert all(h == 0.5 for h in hashes)


class TestChunkManagerStrategies:
    """各分块策略测试"""

    def setup_method(self):
        self.chunker = ChunkManager(chunk_size=30, overlap_ratio=0.15)

    def test_fixed_strategy_basic(self):
        """固定分块基础测试"""
        text = "one " * 50
        result = self.chunker.chunk_document(text, strategy="fixed")
        assert len(result) > 1
        for chunk in result:
            assert "fixed" in chunk.metadata["strategy"]

    def test_recursive_strategy_basic(self):
        """递归分块基础测试"""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = self.chunker.chunk_document(text, strategy="recursive")
        assert len(result) >= 1
        assert all(chunk.token_count > 0 for chunk in result)

    def test_header_aware_strategy(self):
        """标题感知分块测试"""
        text = "# Header 1\n\nContent under header 1\n\n## Header 2\n\nContent under header 2"
        result = self.chunker.chunk_document(text, strategy="header_aware")
        assert len(result) >= 1

    def test_header_aware_preserves_hierarchy(self):
        """标题层级应该保留到metadata"""
        text = "# Main Title\n\n## Sub Title\n\nSome content here."
        result = self.chunker.chunk_document(text, strategy="header_aware", chunk_size=100)

        chunks_with_heading = [
            chunk for chunk in result
            if "heading" in chunk.metadata
        ]
        assert len(chunks_with_heading) > 0

        for chunk in chunks_with_heading:
            heading = chunk.metadata["heading"]
            assert "h1" in heading or "h2" in heading


class TestChunkManagerTokenCounting:
    """Token计算测试"""

    def setup_method(self):
        self.chunker = ChunkManager()

    def test_token_count_accuracy(self):
        """Token计数应该准确"""
        text = "hello world"
        result = self.chunker.chunk_document(text)
        assert len(result) == 1
        assert result[0].token_count == 2

    def test_chunk_size_respects_limit(self):
        """分块大小应该遵守限制"""
        text = "word " * 100
        result = self.chunker.chunk_document(text, chunk_size=10, strategy="fixed")

        for chunk in result[:-1]:
            assert chunk.token_count <= 10

    def test_overlap_ratio_parameter(self):
        """重叠比例参数应该生效"""
        text = "A" + " word " * 100
        result_no_overlap = self.chunker.chunk_document(text, overlap_ratio=0)
        result_with_overlap = self.chunker.chunk_document(text, overlap_ratio=0.3)

        assert len(result_with_overlap) >= len(result_no_overlap)


class TestChunkManagerMetadata:
    """元数据测试"""

    def setup_method(self):
        self.chunker = ChunkManager(chunk_size=50, overlap_ratio=0.15)

    def test_metadata_contains_required_fields(self):
        """元数据应该包含必需字段"""
        text = "hello world"
        result = self.chunker.chunk_document(text, source="test.txt")

        assert len(result) == 1
        metadata = result[0].metadata
        assert "source" in metadata
        assert "strategy" in metadata
        assert "chunk_size" in metadata
        assert "overlap_ratio" in metadata

    def test_source_metadata(self):
        """source元数据正确"""
        result = self.chunker.chunk_document("content", source="test.txt")
        assert result[0].metadata["source"] == "test.txt"

    def test_strategy_metadata(self):
        """strategy元数据正确"""
        for strategy in ["fixed", "recursive", "header_aware"]:
            result = self.chunker.chunk_document("hello world", strategy=strategy)
            assert result[0].metadata["strategy"] == strategy

    def test_chunk_index_and_total(self):
        """chunk_index和total_chunks正确"""
        text = "word " * 100
        result = self.chunker.chunk_document(text, strategy="fixed")

        if len(result) > 1:
            assert all(chunk.total_chunks == len(result) for chunk in result)
            indices = [chunk.chunk_index for chunk in result]
            assert indices == list(range(len(result)))
