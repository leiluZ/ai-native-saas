import hashlib
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
import json

import tiktoken

from .schemas import ChunkResult


class ChunkManager:
    def __init__(self, chunk_size: int = 512, overlap_ratio: float = 0.15):
        self.chunk_size = chunk_size
        self.overlap_ratio = overlap_ratio
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def chunk_document(
        self,
        content: str,
        source: str = "",
        strategy: Literal["fixed", "recursive", "header_aware"] = "recursive",
        chunk_size: Optional[int] = None,
        overlap_ratio: Optional[float] = None
    ) -> List[ChunkResult]:
        """分块文档"""
        actual_chunk_size = chunk_size or self.chunk_size
        actual_overlap = overlap_ratio or self.overlap_ratio
        overlap_tokens = int(actual_chunk_size * actual_overlap)

        if strategy == "fixed":
            chunks = self._chunk_fixed(content, actual_chunk_size, overlap_tokens)
        elif strategy == "header_aware":
            chunks = self._chunk_header_aware(content, actual_chunk_size, overlap_tokens)
        else:
            chunks = self._chunk_recursive(content, actual_chunk_size, overlap_tokens)

        results = []
        seen_hashes = set()

        for i, chunk in enumerate(chunks):
            chunk_hash = self._compute_hash(chunk)

            if chunk_hash in seen_hashes:
                continue
            seen_hashes.add(chunk_hash)

            results.append(ChunkResult(
                chunk_id=f"{self._compute_hash(source + str(i))[:16]}",
                content=chunk,
                metadata={
                    'source': source,
                    'strategy': strategy,
                    'chunk_size': actual_chunk_size,
                    'overlap_ratio': actual_overlap
                },
                chunk_index=i,
                total_chunks=len(chunks),
                token_count=self._count_tokens(chunk)
            ))

        return results

    def _chunk_fixed(self, content: str, chunk_size: int, overlap_tokens: int) -> List[str]:
        """固定长度分块"""
        tokens = self.encoder.encode(content)
        chunks = []

        for i in range(0, len(tokens), chunk_size - overlap_tokens):
            chunk_tokens = tokens[i:i + chunk_size]
            if chunk_tokens:
                chunks.append(self.encoder.decode(chunk_tokens))

        return chunks

    def _chunk_recursive(self, content: str, chunk_size: int, overlap_tokens: int) -> List[str]:
        """递归分块（按段落、句子、单词）"""
        tokens = self.encoder.encode(content)

        if len(tokens) <= chunk_size:
            return [content]

        chunks = []
        separators = ['\n\n', '\n', '. ', '! ', '? ', '; ', ', ', ' ']

        def split_tokens(tokens, target_size):
            if len(tokens) <= target_size:
                return [tokens]

            for sep in separators:
                sep_tokens = self.encoder.encode(sep)
                if len(sep_tokens) == 0:
                    continue

                for i in range(len(tokens) - target_size, target_size // 2, -1):
                    if tokens[i:i + len(sep_tokens)] == sep_tokens:
                        left = tokens[:i + len(sep_tokens)]
                        right = tokens[i:]
                        return split_tokens(left, target_size) + split_tokens(right, target_size)

            return [tokens[:chunk_size], tokens[chunk_size - overlap_tokens:]]

        token_chunks = split_tokens(tokens, chunk_size)
        return [self.encoder.decode(chunk) for chunk in token_chunks]

    def _chunk_header_aware(self, content: str, chunk_size: int, overlap_tokens: int) -> List[str]:
        """标题感知分块"""
        import re

        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_heading = ""
        current_tokens = 0

        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)')

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                level = len(match.group(1))
                current_heading = match.group(2)

                if current_chunk:
                    chunks.append(('\n'.join(current_chunk), current_heading))
                    current_chunk = []
                    current_tokens = 0

            line_tokens = self._count_tokens(line)

            if current_tokens + line_tokens > chunk_size and current_chunk:
                chunks.append(('\n'.join(current_chunk), current_heading))
                overlap_text = '\n'.join(current_chunk[-2:]) if len(current_chunk) >= 2 else ''
                current_chunk = [overlap_text, line]
                current_tokens = self._count_tokens('\n'.join(current_chunk))
            else:
                current_chunk.append(line)
                current_tokens += line_tokens

        if current_chunk:
            chunks.append(('\n'.join(current_chunk), current_heading))

        return [chunk for chunk, _ in chunks]

    def _count_tokens(self, text: str) -> int:
        """计算 Token 数量"""
        return len(self.encoder.encode(text))

    def _compute_hash(self, text: str) -> str:
        """计算文本哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def export_chunks(self, chunks: List[ChunkResult], output_path: str) -> None:
        """导出分块结果到 JSONL"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.dict(), ensure_ascii=False) + '\n')

    def get_chunk_stats(self, chunks: List[ChunkResult]) -> Dict[str, Any]:
        """获取分块统计信息"""
        if not chunks:
            return {}

        token_counts = [chunk.token_count for chunk in chunks]

        return {
            'total_chunks': len(chunks),
            'total_tokens': sum(token_counts),
            'avg_tokens': int(sum(token_counts) / len(token_counts)),
            'min_tokens': min(token_counts),
            'max_tokens': max(token_counts),
            'p95_tokens': sorted(token_counts)[int(len(token_counts) * 0.95)]
        }
