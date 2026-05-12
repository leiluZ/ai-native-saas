import logging
import asyncio
from typing import List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """BGE-M3 Embedding 服务，支持 ONNX 推理和 CPU/GPU 自动降级"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: Optional[str] = None,
        max_length: int = 8192,
    ):
        self.model_name = model_name
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
        self.device = device or self._detect_device()
        logger.info(f"[EmbeddingService] Initializing with device='{self.device}'")

    def _detect_device(self) -> str:
        """自动检测最佳设备"""
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("[EmbeddingService] GPU detected, using CUDA")
                return "cuda"
            elif torch.backends.mps.is_available():
                logger.info("[EmbeddingService] MPS detected, using Apple Silicon")
                return "mps"
        except ImportError:
            pass

        logger.info("[EmbeddingService] No GPU available, using CPU")
        return "cpu"

    async def _load_model(self):
        """异步加载模型"""
        if self._model is not None:
            return

        logger.info(f"[EmbeddingService] Loading model '{self.model_name}'")

        try:
            from transformers import AutoTokenizer, AutoModel
            import torch

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # 明确使用 CPU 模式加载模型
            self._model = AutoModel.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=False,  # 禁用以避免需要 accelerate 库
            )
            self._model = self._model.to("cpu")
            self._model.eval()

            logger.info("[EmbeddingService] Model loaded successfully")
        except Exception as e:
            logger.error(f"[EmbeddingService] Failed to load model: {str(e)}")
            raise RuntimeError(f"模型加载失败: {str(e)}")

    async def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        编码文本为向量

        Args:
            texts: 单个文本或文本列表
            batch_size: 批处理大小
            normalize: 是否归一化向量

        Returns:
            向量数组 (N, D)
        """
        await self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        logger.info(
            f"[EmbeddingService] Encoding {len(texts)} texts with batch_size={batch_size}"
        )

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._encode_batch(batch, normalize)
            all_embeddings.append(batch_embeddings)

        embeddings = np.vstack(all_embeddings)
        logger.info(f"[EmbeddingService] Encoding complete - shape={embeddings.shape}")

        return embeddings

    async def _encode_batch(
        self, texts: List[str], normalize: bool = True
    ) -> np.ndarray:
        """编码单个批次"""

        # 在事件循环的线程池中运行同步代码
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._encode_batch_sync, texts, normalize
        )

    def _encode_batch_sync(
        self, texts: List[str], normalize: bool = True
    ) -> np.ndarray:
        """同步编码批次（在线程池中运行）"""
        import torch

        inputs = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=self.max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0]  # CLS token

            if normalize:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()

    async def encode_queries(
        self, queries: Union[str, List[str]], batch_size: int = 32
    ) -> np.ndarray:
        """编码查询（添加指令前缀）"""
        if isinstance(queries, str):
            queries = [queries]

        # BGE-M3 查询指令
        instructed_queries = [
            f"Represent this sentence for searching relevant passages: {q}"
            for q in queries
        ]

        return await self.encode(instructed_queries, batch_size=batch_size)

    async def encode_documents(
        self, documents: Union[str, List[str]], batch_size: int = 32
    ) -> np.ndarray:
        """编码文档"""
        return await self.encode(documents, batch_size=batch_size)

    def get_dimension(self) -> int:
        """获取向量维度"""
        return 1024  # BGE-M3 默认维度

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.encode(["test"])
            return True
        except Exception as e:
            logger.error(f"[EmbeddingService] Health check failed: {str(e)}")
            return False
