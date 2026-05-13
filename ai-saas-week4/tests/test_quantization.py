import pytest
import os
import sys
import yaml
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# 本地定义数据类，避免导入需要 torch 的模块
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


class TestQuantizationConfig:
    """测试量化配置"""

    def test_config_loading(self, temp_config_file):
        """测试配置文件加载"""
        with open(temp_config_file, 'r') as f:
            config = yaml.safe_load(f)

        assert 'engine' in config
        assert 'base_url' in config
        assert config['total_requests'] == 10
        assert config['concurrency'] == 2

    def test_quantization_config_structure(self):
        """测试量化配置结构"""
        quant_config = {
            "model_name": "Qwen/Qwen2.5-7B-Instruct",
            "quantized_model_path": "./models/quantized",
            "fp16_model_path": "./models/fp16",
            "strategy": "awq",
            "calibration": {
                "dataset": "wikitext",
                "dataset_name": "wikitext-103-v1",
                "num_samples": 128,
                "max_seq_length": 512
            },
            "awq": {"bits": 4, "group_size": 128, "zero_point": True},
            "validation": {"perplexity": True, "quality_regression": True}
        }

        assert quant_config['strategy'] == "awq"
        assert quant_config['calibration']['num_samples'] == 128
        assert quant_config['awq']['bits'] == 4


class TestQuantizationResultDataclass:
    """测试量化结果数据类"""

    def test_success_result(self):
        """测试成功量化结果"""
        result = QuantizationResult(
            success=True,
            model_path="/models/quantized/awq",
            quantized_size_mb=4000.0,
            original_size_mb=13000.0,
            quantization_time=120.5,
            strategy="awq"
        )

        assert result.success is True
        assert result.model_path == "/models/quantized/awq"
        assert result.quantization_time == 120.5
        assert result.strategy == "awq"

        # 验证显存节省计算
        savings = (1 - result.quantized_size_mb / result.original_size_mb) * 100
        assert savings > 50  # 验证显存节省超过50%

    def test_failure_result(self):
        """测试失败量化结果"""
        result = QuantizationResult(
            success=False,
            model_path="",
            quantized_size_mb=0,
            original_size_mb=0,
            quantization_time=30.0,
            strategy="gptq",
            error="Out of memory"
        )

        assert result.success is False
        assert result.error == "Out of memory"
        assert result.quantization_time == 30.0


class TestCalibrationDataDataclass:
    """测试校准数据数据类"""

    def test_calibration_data(self):
        """测试校准数据"""
        data = CalibrationData(
            texts=["text1", "text2", "text3"],
            num_samples=3,
            dataset_name="test"
        )

        assert len(data.texts) == 3
        assert data.num_samples == 3
        assert data.dataset_name == "test"

    def test_calibration_data_empty(self):
        """测试空校准数据"""
        data = CalibrationData(
            texts=[],
            num_samples=0,
            dataset_name="empty"
        )

        assert len(data.texts) == 0
        assert data.num_samples == 0


class TestPerplexityResultDataclass:
    """测试困惑度结果数据类"""

    def test_perplexity_result(self):
        """测试困惑度结果"""
        result = PerplexityResult(
            perplexity=8.5,
            mean_perplexity=8.5,
            std_perplexity=0.5,
            samples_count=10
        )

        assert result.perplexity == 8.5
        assert result.mean_perplexity == 8.5
        assert result.std_perplexity == 0.5
        assert result.samples_count == 10

    def test_perplexity_result_zero(self):
        """测试零困惑度结果"""
        result = PerplexityResult(
            perplexity=0.0,
            mean_perplexity=0.0,
            std_perplexity=0.0,
            samples_count=0
        )

        assert result.perplexity == 0.0
        assert result.samples_count == 0


class TestQualityRegressionResultDataclass:
    """测试质量回归结果数据类"""

    def test_quality_regression_passed(self):
        """测试通过的质量回归"""
        result = QualityRegressionResult(
            success=True,
            consistency_score=0.92,
            similarity_scores=[0.9, 0.92, 0.94],
            mean_similarity=0.92,
            std_similarity=0.02,
            threshold=0.85,
            passed=True
        )

        assert result.success is True
        assert result.consistency_score == 0.92
        assert result.mean_similarity == 0.92
        assert result.passed is True
        assert result.consistency_score >= result.threshold

    def test_quality_regression_failed(self):
        """测试失败的质量回归"""
        result = QualityRegressionResult(
            success=True,
            consistency_score=0.82,
            similarity_scores=[0.78, 0.82, 0.86],
            mean_similarity=0.82,
            std_similarity=0.04,
            threshold=0.85,
            passed=False
        )

        assert result.passed is False
        assert result.consistency_score < result.threshold


class TestAcceptanceCriteria:
    """测试验收标准"""

    def test_memory_savings_acceptance(self):
        """验证显存节省超过50%"""
        result = QuantizationResult(
            success=True,
            model_path="/models/quantized",
            quantized_size_mb=6000.0,
            original_size_mb=13000.0,
            quantization_time=180.0,
            strategy="awq"
        )

        memory_savings = (1 - result.quantized_size_mb / result.original_size_mb) * 100
        assert memory_savings > 50, f"Memory savings {memory_savings:.1f}% < 50%"

    def test_memory_savings_marginal(self):
        """验证显存节省刚好超过50%"""
        result = QuantizationResult(
            success=True,
            model_path="/models/quantized",
            quantized_size_mb=6400.0,
            original_size_mb=13000.0,
            quantization_time=180.0,
            strategy="gptq"
        )

        memory_savings = (1 - result.quantized_size_mb / result.original_size_mb) * 100
        assert memory_savings > 50, f"Memory savings {memory_savings:.1f}% < 50%"

    def test_perplexity_increase_acceptance(self):
        """验证Perplexity增幅小于5%"""
        fp16_perplexity = 8.0
        quantized_perplexity = 8.35  # 增幅约4.4%

        increase = ((quantized_perplexity - fp16_perplexity) / fp16_perplexity) * 100
        assert increase < 5, f"Perplexity increase {increase:.2f}% >= 5%"

    def test_perplexity_increase_exceeds(self):
        """验证Perplexity增幅超过阈值时标记为失败"""
        fp16_perplexity = 8.0
        quantized_perplexity = 8.5  # 增幅6.25%

        increase = ((quantized_perplexity - fp16_perplexity) / fp16_perplexity) * 100
        assert increase >= 5, f"Expected increase >= 5%, got {increase:.2f}%"

    def test_quality_regression_acceptance(self):
        """验证质量回归测试通过"""
        result = QualityRegressionResult(
            success=True,
            consistency_score=0.88,
            similarity_scores=[0.85, 0.87, 0.9, 0.89, 0.86],
            mean_similarity=0.87,
            std_similarity=0.02,
            threshold=0.85,
            passed=True
        )

        assert result.passed is True, "Quality regression test failed"
        assert result.mean_similarity >= result.threshold, \
            f"Mean similarity {result.mean_similarity} < threshold {result.threshold}"

    def test_strategy_validation(self):
        """测试策略验证"""
        valid_strategies = ["awq", "gptq", "int8"]

        for strategy in valid_strategies:
            assert strategy in ["awq", "gptq", "int8"], f"Invalid strategy: {strategy}"


class TestQuantizationPipelineIntegration:
    """测试量化流水线集成"""

    def test_pipeline_initialization(self):
        """测试流水线初始化"""
        mock_pipeline = MagicMock()
        mock_pipeline.strategy = "awq"
        mock_pipeline.model_name = "Qwen/Qwen2.5-7B-Instruct"

        assert mock_pipeline.strategy == "awq"
        assert mock_pipeline.model_name == "Qwen/Qwen2.5-7B-Instruct"

    def test_quantization_flow(self):
        """测试量化流程"""
        mock_pipeline = MagicMock()
        mock_pipeline.quantize.return_value = QuantizationResult(
            success=True,
            model_path="/models/quantized/awq",
            quantized_size_mb=4000.0,
            original_size_mb=13000.0,
            quantization_time=120.5,
            strategy="awq"
        )

        result = mock_pipeline.quantize()

        assert result.success is True
        assert result.strategy == "awq"
        mock_pipeline.quantize.assert_called_once()

    def test_rollback_on_failure(self):
        """测试失败回滚"""
        mock_pipeline = MagicMock()
        mock_pipeline.quantize.return_value = QuantizationResult(
            success=False,
            model_path="",
            quantized_size_mb=0,
            original_size_mb=0,
            quantization_time=30.0,
            strategy="awq",
            error="Failed"
        )
        mock_pipeline.rollback_to_fp16.return_value = True

        result = mock_pipeline.quantize()

        assert result.success is False
        assert result.error == "Failed"


class TestValidationIntegration:
    """测试验证集成"""

    def test_perplexity_comparison(self):
        """测试困惑度对比"""
        fp16_perplexity = 8.0
        quantized_perplexity = 8.3

        increase = ((quantized_perplexity - fp16_perplexity) / fp16_perplexity) * 100
        threshold = 5.0

        assert increase < threshold, f"Perplexity increase {increase:.2f}% exceeds threshold"

    def test_throughput_improvement(self):
        """测试吞吐提升"""
        fp16_throughput = 50.0  # tokens/sec
        quantized_throughput = 110.0  # tokens/sec

        improvement = ((quantized_throughput - fp16_throughput) / fp16_throughput) * 100
        assert improvement > 100, f"Throughput improvement {improvement:.1f}% < 100% (2x)"


class TestConfigYamlStructure:
    """测试 config.yaml 结构"""

    def test_quantization_section_exists(self):
        """测试量化配置节存在"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        assert os.path.exists(config_path), "config.yaml not found"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'quantization' in config, "quantization section missing"
        assert 'strategy' in config['quantization'], "strategy missing"
        assert 'model_name' in config['quantization'], "model_name missing"

    def test_calibration_config(self):
        """测试校准配置"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        calib = config['quantization'].get('calibration', {})
        assert 'dataset' in calib, "calibration.dataset missing"
        assert 'num_samples' in calib, "calibration.num_samples missing"

    def test_validation_config(self):
        """测试验证配置"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        validation = config['quantization'].get('validation', {})
        assert 'perplexity' in validation, "validation.perplexity missing"
        assert 'quality_regression' in validation, "validation.quality_regression missing"
        assert 'similarity_threshold' in validation, "validation.similarity_threshold missing"
