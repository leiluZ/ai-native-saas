import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset

logger = logging.getLogger(__name__)


@dataclass
class QuantizationResult:
    success: bool
    model_path: str
    quantized_size_mb: float
    original_size_mb: float
    quantization_time: float
    strategy: str
    error: Optional[str] = None


@dataclass
class CalibrationData:
    texts: List[str]
    num_samples: int
    dataset_name: str


class QuantizationPipeline:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "Qwen/Qwen2.5-7B-Instruct")
        self.quantized_model_path = Path(config.get("quantized_model_path", "./models/quantized"))
        self.fp16_model_path = Path(config.get("fp16_model_path", "./models/fp16"))
        self.strategy = config.get("strategy", "awq")

        self.quantized_model_path.mkdir(parents=True, exist_ok=True)
        self.fp16_model_path.mkdir(parents=True, exist_ok=True)

    def _get_model_size(self, model_path: Path) -> float:
        total_size = 0
        for file in model_path.rglob("*.bin") + model_path.rglob("*.safetensors"):
            total_size += file.stat().st_size
        return total_size / (1024 * 1024)

    def download_calibration_data(self) -> CalibrationData:
        """自动下载校准数据集"""
        calib_config = self.config.get("calibration", {})
        dataset_name = calib_config.get("dataset_name", "wikitext-103-v1")
        num_samples = calib_config.get("num_samples", 128)

        logger.info(f"Downloading calibration dataset: {dataset_name}")
        start_time = time.time()

        try:
            dataset = load_dataset("wikitext", dataset_name, split="train")

            texts = []
            for item in dataset:
                if item["text"] and len(item["text"].strip()) > 100:
                    texts.append(item["text"].strip())
                if len(texts) >= num_samples:
                    break

            elapsed = time.time() - start_time
            logger.info(f"Calibration data downloaded in {elapsed:.2f}s, {len(texts)} samples")

            return CalibrationData(
                texts=texts,
                num_samples=len(texts),
                dataset_name=dataset_name
            )
        except Exception as e:
            logger.error(f"Failed to download calibration data: {e}")
            raise

    def _quantize_awq(self, model, tokenizer, calibration_texts: List[str]) -> str:
        """使用 AWQ 量化模型"""
        from awq import AutoAWQForCausalLM
        from awq.utils.fused_utils import fuse_modules

        awq_config = self.config.get("awq", {})
        bits = awq_config.get("bits", 4)
        group_size = awq_config.get("group_size", 128)

        output_path = self.quantized_model_path / "awq"
        output_path.mkdir(exist_ok=True)

        logger.info(f"Starting AWQ quantization: {bits} bits, group_size={group_size}")

        model = AutoAWQForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto",
            torch_dtype=torch.float16
        )

        model.quantize(tokenizer, calibration_texts=calibration_texts, bits=bits, group_size=group_size)
        model.save_quantized(output_path)
        tokenizer.save_pretrained(output_path)

        return str(output_path)

    def _quantize_gptq(self, model, tokenizer, calibration_texts: List[str]) -> str:
        """使用 GPTQ 量化模型"""
        from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig

        gptq_config = self.config.get("gptq", {})
        bits = gptq_config.get("bits", 4)
        group_size = gptq_config.get("group_size", 128)
        act_order = gptq_config.get("act_order", True)

        output_path = self.quantized_model_path / "gptq"
        output_path.mkdir(exist_ok=True)

        logger.info(f"Starting GPTQ quantization: {bits} bits, group_size={group_size}, act_order={act_order}")

        quantize_config = BaseQuantizeConfig(
            bits=bits,
            group_size=group_size,
            act_order=act_order
        )

        model = AutoGPTQForCausalLM.from_pretrained(
            self.model_name,
            quantize_config=quantize_config,
            device_map="auto",
            torch_dtype=torch.float16
        )

        model.quantize(calibration_texts)
        model.save_quantized(output_path)
        tokenizer.save_pretrained(output_path)

        return str(output_path)

    def _quantize_int8(self, model, tokenizer) -> str:
        """使用 bitsandbytes INT8 量化模型"""
        from transformers import BitsAndBytesConfig

        int8_config = self.config.get("int8", {})

        output_path = self.quantized_model_path / "int8"
        output_path.mkdir(exist_ok=True)

        logger.info("Starting INT8 quantization")

        bnb_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0
        )

        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            quantization_config=bnb_config,
            device_map="auto"
        )

        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)

        return str(output_path)

    def quantize(self) -> QuantizationResult:
        """执行量化流程"""
        start_time = time.time()

        try:
            logger.info(f"Starting quantization with strategy: {self.strategy}")

            tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            if self.strategy in ["awq", "gptq"]:
                calibration_data = self.download_calibration_data()
            else:
                calibration_data = None

            original_size = self._get_model_size(self.fp16_model_path)

            if self.strategy == "awq":
                model_path = self._quantize_awq(None, tokenizer, calibration_data.texts if calibration_data else [])
            elif self.strategy == "gptq":
                model_path = self._quantize_gptq(None, tokenizer, calibration_data.texts if calibration_data else [])
            elif self.strategy == "int8":
                model_path = self._quantize_int8(None, tokenizer)
            else:
                raise ValueError(f"Unknown quantization strategy: {self.strategy}")

            quantized_size = self._get_model_size(Path(model_path))
            quantization_time = time.time() - start_time

            logger.info(f"Quantization completed in {quantization_time:.2f}s")
            logger.info(f"Original size: {original_size:.2f} MB, Quantized size: {quantized_size:.2f} MB")
            logger.info(f"Memory savings: {(1 - quantized_size / original_size) * 100:.1f}%")

            return QuantizationResult(
                success=True,
                model_path=model_path,
                quantized_size_mb=quantized_size,
                original_size_mb=original_size,
                quantization_time=quantization_time,
                strategy=self.strategy
            )

        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return QuantizationResult(
                success=False,
                model_path="",
                quantized_size_mb=0,
                original_size_mb=0,
                quantization_time=time.time() - start_time,
                strategy=self.strategy,
                error=str(e)
            )

    def load_quantized_model(self, strategy: Optional[str] = None):
        """加载量化模型"""
        strategy = strategy or self.strategy
        model_path = self.quantized_model_path / strategy

        if not model_path.exists():
            raise FileNotFoundError(f"Quantized model not found at {model_path}")

        logger.info(f"Loading quantized model from {model_path}")

        if strategy == "awq":
            from awq import AutoAWQForCausalLM
            model = AutoAWQForCausalLM.from_quantized(
                str(model_path),
                device_map="auto"
            )
        elif strategy == "gptq":
            from auto_gptq import AutoGPTQForCausalLM
            model = AutoGPTQForCausalLM.from_quantized(
                str(model_path),
                device_map="auto",
                use_safetensors=True
            )
        elif strategy == "int8":
            from transformers import AutoModelForCausalLM, BitsAndBytesConfig
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)
            model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                quantization_config=bnb_config,
                device_map="auto"
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        return model, tokenizer

    def rollback_to_fp16(self) -> bool:
        """回滚到 FP16 权重"""
        try:
            logger.info("Rolling back to FP16 weights")

            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="auto"
            )

            model.save_pretrained(self.fp16_model_path)
            tokenizer.save_pretrained(self.fp16_model_path)

            logger.info("Successfully rolled back to FP16")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False
