import math
import logging
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class PerplexityResult:
    perplexity: float
    mean_perplexity: float
    std_perplexity: float
    samples_count: int


@dataclass
class QualityRegressionResult:
    success: bool
    consistency_score: float
    similarity_scores: List[float]
    mean_similarity: float
    std_similarity: float
    threshold: float
    passed: bool


@dataclass
class ValidationResult:
    perplexity: Optional[PerplexityResult] = None
    quality_regression: Optional[QualityRegressionResult] = None
    overall_passed: bool = False


class ModelValidator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_config = config.get("validation", {})
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

    def calculate_perplexity(self, model, tokenizer, texts: List[str]) -> PerplexityResult:
        """计算模型的 Perplexity"""
        logger.info("Calculating perplexity...")

        model.eval()
        perplexities = []

        with torch.no_grad():
            for text in texts:
                if len(text.strip()) < 50:
                    continue

                try:
                    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
                    inputs = {k: v.to(model.device) for k, v in inputs.items()}

                    outputs = model(**inputs, labels=inputs["input_ids"])
                    loss = outputs.loss
                    perplexity = math.exp(loss.item())
                    perplexities.append(perplexity)
                except Exception as e:
                    logger.warning(f"Failed to calculate perplexity for text: {e}")
                    continue

        if not perplexities:
            return PerplexityResult(
                perplexity=0.0,
                mean_perplexity=0.0,
                std_perplexity=0.0,
                samples_count=0
            )

        mean_ppl = np.mean(perplexities)
        std_ppl = np.std(perplexities)

        logger.info(f"Perplexity calculated: mean={mean_ppl:.2f}, std={std_ppl:.2f}, samples={len(perplexities)}")

        return PerplexityResult(
            perplexity=mean_ppl,
            mean_perplexity=mean_ppl,
            std_perplexity=std_ppl,
            samples_count=len(perplexities)
        )

    def generate_text(self, model, tokenizer, prompt: str, max_new_tokens: int = 128) -> str:
        """生成文本"""
        model.eval()

        with torch.no_grad():
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.95
            )
            generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
            return generated.replace(prompt, "").strip()

    def calculate_similarity(self, texts: List[str]) -> List[float]:
        """计算文本之间的相似度"""
        embeddings = self.sentence_model.encode(texts)

        similarities = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                similarities.append(sim)

        return similarities

    def run_quality_regression(self, model, tokenizer, prompt: str, num_samples: int = 10) -> QualityRegressionResult:
        """运行质量回归测试：相同 Prompt 生成多次，计算一致性"""
        logger.info(f"Running quality regression test with {num_samples} samples...")

        threshold = self.validation_config.get("similarity_threshold", 0.85)
        generated_texts = []

        for i in range(num_samples):
            generated = self.generate_text(model, tokenizer, prompt)
            generated_texts.append(generated)
            logger.debug(f"Generated sample {i + 1}: {generated[:50]}...")

        similarities = self.calculate_similarity(generated_texts)

        if not similarities:
            return QualityRegressionResult(
                success=False,
                consistency_score=0.0,
                similarity_scores=[],
                mean_similarity=0.0,
                std_similarity=0.0,
                threshold=threshold,
                passed=False
            )

        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        passed = mean_sim >= threshold

        logger.info(f"Quality regression completed: mean_similarity={mean_sim:.4f}, threshold={threshold}, passed={passed}")

        return QualityRegressionResult(
            success=True,
            consistency_score=mean_sim,
            similarity_scores=similarities,
            mean_similarity=mean_sim,
            std_similarity=std_sim,
            threshold=threshold,
            passed=passed
        )

    def validate(self, model, tokenizer, calibration_texts: List[str], test_prompt: str) -> ValidationResult:
        """执行完整验证流程"""
        result = ValidationResult()

        if self.validation_config.get("perplexity", True):
            result.perplexity = self.calculate_perplexity(model, tokenizer, calibration_texts)

        if self.validation_config.get("quality_regression", True):
            result.quality_regression = self.run_quality_regression(
                model,
                tokenizer,
                test_prompt,
                num_samples=self.validation_config.get("regression_samples", 10)
            )

        result.overall_passed = (
            (result.perplexity is None or result.perplexity.samples_count > 0) and
            (result.quality_regression is None or result.quality_regression.passed)
        )

        return result

    def compare_perplexity(self, fp16_perplexity: float, quantized_perplexity: float) -> Dict[str, Any]:
        """对比 FP16 和量化模型的 Perplexity"""
        increase = ((quantized_perplexity - fp16_perplexity) / fp16_perplexity) * 100
        threshold = 5.0  # Perplexity 增幅阈值

        return {
            "fp16": fp16_perplexity,
            "quantized": quantized_perplexity,
            "increase_percent": increase,
            "within_threshold": increase < threshold,
            "threshold": threshold
        }
