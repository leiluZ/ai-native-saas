import argparse
import logging
import time
import yaml
from pathlib import Path
from typing import Dict, Any

import torch

from .quantization import QuantizationPipeline
from .validation import ModelValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("quantization.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_gpu_memory_info() -> Dict[str, float]:
    """获取 GPU 显存信息"""
    if torch.cuda.is_available():
        return {
            "total_mb": torch.cuda.get_device_properties(0).total_memory / (1024 * 1024),
            "used_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "free_mb": torch.cuda.memory_free(0) / (1024 * 1024)
        }
    return {}


def print_memory_snapshot():
    """打印显存快照"""
    memory_info = get_gpu_memory_info()
    logger.info("=== GPU Memory Snapshot ===")
    for key, value in memory_info.items():
        logger.info(f"{key}: {value:.2f} MB")
    logger.info("=" * 40)


def print_quantization_report(result, validation_result=None, perplexity_comparison=None):
    """打印量化报告"""
    logger.info("\n" + "=" * 60)
    logger.info("QUANTIZATION REPORT")
    logger.info("=" * 60)

    logger.info(f"\nStrategy: {result.strategy}")
    logger.info(f"Status: {'SUCCESS' if result.success else 'FAILED'}")

    if result.success:
        logger.info(f"\nTiming:")
        logger.info(f"  Quantization Time: {result.quantization_time:.2f} seconds")

        logger.info(f"\nMemory Usage:")
        logger.info(f"  Original Size: {result.original_size_mb:.2f} MB")
        logger.info(f"  Quantized Size: {result.quantized_size_mb:.2f} MB")
        if result.original_size_mb > 0:
            savings = (1 - result.quantized_size_mb / result.original_size_mb) * 100
            logger.info(f"  Memory Savings: {savings:.1f}%")

        logger.info(f"\nOutput Path: {result.model_path}")

        if validation_result:
            logger.info(f"\nValidation Results:")

            if validation_result.perplexity:
                logger.info(f"  Perplexity:")
                logger.info(f"    Mean: {validation_result.perplexity.mean_perplexity:.2f}")
                logger.info(f"    Std: {validation_result.perplexity.std_perplexity:.2f}")
                logger.info(f"    Samples: {validation_result.perplexity.samples_count}")

            if validation_result.quality_regression:
                logger.info(f"  Quality Regression:")
                logger.info(f"    Mean Similarity: {validation_result.quality_regression.mean_similarity:.4f}")
                logger.info(f"    Threshold: {validation_result.quality_regression.threshold}")
                logger.info(f"    Passed: {validation_result.quality_regression.passed}")

            logger.info(f"  Overall: {'PASSED' if validation_result.overall_passed else 'FAILED'}")

        if perplexity_comparison:
            logger.info(f"\nPerplexity Comparison:")
            logger.info(f"  FP16: {perplexity_comparison['fp16']:.2f}")
            logger.info(f"  Quantized: {perplexity_comparison['quantized']:.2f}")
            logger.info(f"  Increase: {perplexity_comparison['increase_percent']:.2f}%")
            logger.info(f"  Within Threshold ({perplexity_comparison['threshold']}%): {perplexity_comparison['within_threshold']}")

    else:
        logger.info(f"\nError: {result.error}")

    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LLM Model Quantization Pipeline")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--strategy", type=str, choices=["awq", "gptq", "int8"], help="Quantization strategy")
    parser.add_argument("--validate", action="store_true", help="Run validation after quantization")
    parser.add_argument("--rollback-on-failure", action="store_true", help="Rollback to FP16 on failure")

    args = parser.parse_args()

    config = load_config(args.config)
    quant_config = config.get("quantization", {})

    if args.strategy:
        quant_config["strategy"] = args.strategy

    pipeline = QuantizationPipeline(quant_config)
    validator = ModelValidator(quant_config)

    logger.info("=" * 60)
    logger.info(f"Starting Quantization Pipeline with {quant_config['strategy'].upper()}")
    logger.info("=" * 60)

    print_memory_snapshot()
    start_time = time.time()

    try:
        quantization_result = pipeline.quantize()

        if quantization_result.success:
            logger.info("Quantization completed successfully")

            if args.validate:
                logger.info("Loading quantized model for validation...")
                model, tokenizer = pipeline.load_quantized_model()

                calibration_data = pipeline.download_calibration_data()

                test_prompt = "Explain the concept of machine learning in simple terms."
                validation_result = validator.validate(model, tokenizer, calibration_data.texts[:10], test_prompt)

                print_quantization_report(quantization_result, validation_result)

                if not validation_result.overall_passed:
                    logger.warning("Validation failed!")
                    if quant_config.get("fallback", {}).get("rollback_on_failure", False) or args.rollback_on_failure:
                        logger.info("Initiating rollback to FP16...")
                        pipeline.rollback_to_fp16()
            else:
                print_quantization_report(quantization_result)

        else:
            logger.error(f"Quantization failed: {quantization_result.error}")
            if quant_config.get("fallback", {}).get("rollback_on_failure", False) or args.rollback_on_failure:
                logger.info("Initiating rollback to FP16...")
                pipeline.rollback_to_fp16()

    except Exception as e:
        logger.error(f"Pipeline failed with exception: {e}")
        if quant_config.get("fallback", {}).get("rollback_on_failure", False) or args.rollback_on_failure:
            logger.info("Initiating rollback to FP16...")
            pipeline.rollback_to_fp16()

    total_time = time.time() - start_time
    logger.info(f"\nTotal pipeline time: {total_time:.2f} seconds")
    print_memory_snapshot()


if __name__ == "__main__":
    main()
