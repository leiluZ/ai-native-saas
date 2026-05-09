#!/usr/bin/env python3
"""RAG 参数自动调优器 - 基于 RAGAS 评估的参数寻优"""

import json
import os
import csv
import yaml
import random
import itertools
import concurrent.futures
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns

from ragas_evaluate import (
    load_test_set,
    RateLimitedLLM,
    RAGASEvaluator,
    generate_report,
    TestSample,
    EvaluationResult,
    ReportSummary
)


@dataclass
class TuningConfig:
    """调优配置参数"""
    chunk_size: int
    chunk_overlap: int
    top_k: int
    rerank_threshold: float
    similarity_threshold: float


@dataclass
class TuningResult:
    """调优结果"""
    config: TuningConfig
    faithfulness: float
    answer_relevance: float
    context_precision: float
    weighted_score: float
    duration: float
    memory_usage: float = 0.0


class RAGTuner:
    """RAG 参数自动调优器"""

    def __init__(
        self,
        test_set_path: str = "test_set.json",
        use_vllm: bool = False,
        vllm_url: str = "http://localhost:8000/v1",
        max_workers: int = 3,
        early_stop_threshold: float = 0.85,
        early_stop_patience: int = 2
    ):
        self.test_set_path = test_set_path
        self.use_vllm = use_vllm
        self.vllm_url = vllm_url
        self.max_workers = max_workers
        self.early_stop_threshold = early_stop_threshold
        self.early_stop_patience = early_stop_patience

        # 加载测试集
        if not os.path.exists(test_set_path):
            self._generate_example_test_set(test_set_path)
        self.samples = load_test_set(test_set_path)

        # 参数搜索空间
        self.param_grid = {
            'chunk_size': [256, 512, 768, 1024],
            'chunk_overlap': [32, 64, 128],
            'top_k': [3, 5, 7, 10],
            'rerank_threshold': [0.5, 0.6, 0.7, 0.8],
            'similarity_threshold': [0.7, 0.75, 0.8, 0.85]
        }

        # 最佳结果跟踪
        self.best_result: Optional[TuningResult] = None
        self.no_improve_count = 0

    def _generate_example_test_set(self, file_path: str):
        """生成示例测试集"""
        example_data = [
            {
                "question": "什么是 RAG 技术？",
                "answer": "RAG（Retrieval-Augmented Generation）是一种结合检索增强生成技术。",
                "context": [
                    "RAG 即 Retrieval-Augmented Generation，是一种检索增强生成技术。",
                    "RAG 结合了信息检索和大型语言模型的生成能力。",
                    "通过检索外部知识库，可以为生成模型提供最新、准确的信息。"
                ]
            },
            {
                "question": "LangChain 是什么？",
                "answer": "LangChain 是一个用于构建基于语言模型的应用程序的框架。",
                "context": [
                    "LangChain 是一个开源框架，用于开发由语言模型驱动的应用程序。",
                    "它提供了与多种 LLM 提供商的集成。",
                    "LangChain 支持文档加载、分割、检索和生成等功能。"
                ]
            },
            {
                "question": "向量数据库的主要用途是什么？",
                "answer": "向量数据库主要用于存储和检索高维向量数据。",
                "context": [
                    "向量数据库是专门设计用于存储和查询向量嵌入的数据库。",
                    "它们支持高效的相似度搜索。",
                    "常见的向量数据库包括 Pinecone、Chroma、FAISS 等。"
                ]
            }
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(example_data, f, ensure_ascii=False, indent=2)

    def calculate_weighted_score(self, report: ReportSummary) -> float:
        """计算加权综合分"""
        return (
            0.4 * report.avg_faithfulness +
            0.4 * report.avg_answer_relevance +
            0.2 * report.avg_context_precision
        )

    def evaluate_config(self, config: TuningConfig) -> Tuple[TuningResult, ReportSummary]:
        """评估单个配置"""
        start_time = time.time()

        # 模拟 RAG 配置评估
        # 实际场景中这里会调用真实的 RAG 管道
        llm = RateLimitedLLM(use_vllm=self.use_vllm, vllm_url=self.vllm_url)
        evaluator = RAGASEvaluator(llm)

        results: List[EvaluationResult] = []
        for sample in self.samples:
            result = evaluator.evaluate_sample(sample)
            results.append(result)

        report = generate_report(results)
        weighted_score = self.calculate_weighted_score(report)
        duration = time.time() - start_time

        # 模拟显存使用（实际场景中需要监控 GPU 显存）
        memory_usage = self._estimate_memory_usage(config)

        return TuningResult(
            config=config,
            faithfulness=report.avg_faithfulness,
            answer_relevance=report.avg_answer_relevance,
            context_precision=report.avg_context_precision,
            weighted_score=weighted_score,
            duration=duration,
            memory_usage=memory_usage
        ), report

    def _estimate_memory_usage(self, config: TuningConfig) -> float:
        """估算显存使用（简化模型）"""
        base_memory = 2.0  # GB
        chunk_factor = config.chunk_size / 512
        top_k_factor = config.top_k / 5
        return base_memory * chunk_factor * top_k_factor

    def generate_param_combinations(self, sample_ratio: float = 1.0) -> List[TuningConfig]:
        """生成参数组合，支持随机采样降维"""
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())

        # 生成所有组合
        all_combinations = list(itertools.product(*values))

        # 随机采样降维
        if sample_ratio < 1.0:
            sample_size = max(1, int(len(all_combinations) * sample_ratio))
            all_combinations = random.sample(all_combinations, sample_size)

        # 转换为 TuningConfig 对象
        configs = []
        for combo in all_combinations:
            config_dict = dict(zip(keys, combo))
            configs.append(TuningConfig(**config_dict))

        return configs

    def run_tuning(
        self,
        sample_ratio: float = 1.0,
        log_file: str = "tuning_log.csv"
    ) -> Tuple[TuningResult, List[TuningResult]]:
        """运行参数调优"""
        print("=" * 60)
        print("RAG 参数自动调优器")
        print("=" * 60)
        print(f"测试样本数: {len(self.samples)}")
        print(f"参数组合数: {len(self.param_grid)} 维度")
        print(f"采样比例: {sample_ratio * 100:.0f}%")
        print(f"并发线程数: {self.max_workers}")
        print(f"早停阈值: {self.early_stop_threshold}")
        print(f"早停耐心: {self.early_stop_patience} 轮")
        print("=" * 60)

        # 生成参数组合
        configs = self.generate_param_combinations(sample_ratio)
        print(f"待评估配置数: {len(configs)}")

        # 初始化日志文件
        self._init_log_file(log_file)

        all_results: List[TuningResult] = []

        # 分批并发执行
        batch_size = self.max_workers
        for i in range(0, len(configs), batch_size):
            batch = configs[i:i + batch_size]

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.evaluate_config, config): config for config in batch}

                for future in concurrent.futures.as_completed(futures):
                    config = futures[future]
                    try:
                        result, report = future.result()
                        all_results.append(result)

                        # 记录日志
                        self._log_result(result, log_file)

                        # 更新最佳结果
                        if self.best_result is None or result.weighted_score > self.best_result.weighted_score:
                            self.best_result = result
                            self.no_improve_count = 0
                            print(f"\n🎉 发现更佳配置 (加权分: {result.weighted_score:.4f})")
                            print(f"   配置: chunk_size={config.chunk_size}, chunk_overlap={config.chunk_overlap}, "
                                  f"top_k={config.top_k}, rerank_threshold={config.rerank_threshold}, "
                                  f"similarity_threshold={config.similarity_threshold}")
                        else:
                            self.no_improve_count += 1

                        # 检查早停条件
                        if self.best_result.weighted_score >= self.early_stop_threshold:
                            print(f"\n✅ 达到阈值 {self.early_stop_threshold}，提前终止")
                            break

                        if self.no_improve_count >= self.early_stop_patience:
                            print(f"\n⚠️ 连续 {self.early_stop_patience} 轮无提升，提前终止")
                            break

                    except Exception as e:
                        print(f"❌ 配置 {config} 评估失败: {str(e)}")

            if self.best_result.weighted_score >= self.early_stop_threshold or \
               self.no_improve_count >= self.early_stop_patience:
                break

        return self.best_result, all_results

    def _init_log_file(self, log_file: str):
        """初始化日志文件"""
        with open(log_file, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "chunk_size", "chunk_overlap", "top_k",
                "rerank_threshold", "similarity_threshold",
                "faithfulness", "answer_relevance", "context_precision",
                "weighted_score", "duration", "memory_usage"
            ])

    def _log_result(self, result: TuningResult, log_file: str):
        """记录评估结果到 CSV"""
        with open(log_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                result.config.chunk_size,
                result.config.chunk_overlap,
                result.config.top_k,
                result.config.rerank_threshold,
                result.config.similarity_threshold,
                result.faithfulness,
                result.answer_relevance,
                result.context_precision,
                result.weighted_score,
                result.duration,
                result.memory_usage
            ])

    def export_best_config(self, file_path: str = "best_config.yaml"):
        """导出最佳配置到 YAML"""
        if not self.best_result:
            print("❌ 没有找到最佳配置")
            return

        config_data = {
            "best_config": {
                "chunk_size": self.best_result.config.chunk_size,
                "chunk_overlap": self.best_result.config.chunk_overlap,
                "top_k": self.best_result.config.top_k,
                "rerank_threshold": self.best_result.config.rerank_threshold,
                "similarity_threshold": self.best_result.config.similarity_threshold
            },
            "scores": {
                "faithfulness": self.best_result.faithfulness,
                "answer_relevance": self.best_result.answer_relevance,
                "context_precision": self.best_result.context_precision,
                "weighted_score": self.best_result.weighted_score
            },
            "metrics": {
                "duration": self.best_result.duration,
                "memory_usage_gb": self.best_result.memory_usage
            },
            "timestamp": datetime.now().isoformat()
        }

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        print(f"\n📄 最佳配置已导出到: {file_path}")

    def generate_charts(self, results: List[TuningResult], output_dir: str = "charts"):
        """生成分数对比图表"""
        os.makedirs(output_dir, exist_ok=True)

        # 按加权分数排序
        results.sort(key=lambda x: x.weighted_score, reverse=True)

        # 1. 分数分布直方图
        plt.figure(figsize=(10, 6))
        scores = [r.weighted_score for r in results]
        sns.histplot(scores, bins=20, kde=True, color='skyblue')
        plt.title('Weighted Score Distribution')
        plt.xlabel('Weighted Score')
        plt.ylabel('Count')
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(output_dir, 'score_distribution.png'), dpi=100, bbox_inches='tight')
        plt.close()

        # 2. 分数对比条形图（Top 10 配置）
        plt.figure(figsize=(12, 6))
        top_results = results[:10]
        config_labels = [f"CS{r.config.chunk_size}_TK{r.config.top_k}" for r in top_results]

        x = range(len(top_results))
        width = 0.25

        plt.bar([i - width for i in x], [r.faithfulness for r in top_results], width, label='Faithfulness')
        plt.bar(x, [r.answer_relevance for r in top_results], width, label='Answer Relevance')
        plt.bar([i + width for i in x], [r.context_precision for r in top_results], width, label='Context Precision')

        plt.title('Top 10 Configurations Comparison')
        plt.xlabel('Configuration')
        plt.ylabel('Score')
        plt.xticks(x, config_labels, rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'config_comparison.png'), dpi=100, bbox_inches='tight')
        plt.close()

        # 3. 参数相关性热力图
        param_values = defaultdict(list)
        for r in results:
            param_values['chunk_size'].append(r.config.chunk_size)
            param_values['chunk_overlap'].append(r.config.chunk_overlap)
            param_values['top_k'].append(r.config.top_k)
            param_values['rerank_threshold'].append(r.config.rerank_threshold)
            param_values['similarity_threshold'].append(r.config.similarity_threshold)
            param_values['weighted_score'].append(r.weighted_score)

        import pandas as pd
        df = pd.DataFrame(param_values)
        corr = df.corr()

        plt.figure(figsize=(10, 8))
        sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Parameter Correlation Heatmap')
        plt.savefig(os.path.join(output_dir, 'param_correlation.png'), dpi=100, bbox_inches='tight')
        plt.close()

        print(f"\n📊 图表已生成到: {output_dir}/")

    def print_summary(self, best_result: TuningResult, all_results: List[TuningResult]):
        """打印调优总结"""
        print("\n" + "=" * 60)
        print("调优结果总结")
        print("=" * 60)

        print(f"\n总评估配置数: {len(all_results)}")
        print(f"最佳加权分数: {best_result.weighted_score:.4f}")

        print("\n最佳配置参数:")
        print(f"  - chunk_size: {best_result.config.chunk_size}")
        print(f"  - chunk_overlap: {best_result.config.chunk_overlap}")
        print(f"  - top_k: {best_result.config.top_k}")
        print(f"  - rerank_threshold: {best_result.config.rerank_threshold}")
        print(f"  - similarity_threshold: {best_result.config.similarity_threshold}")

        print("\n最佳配置得分:")
        print(f"  - Faithfulness: {best_result.faithfulness:.4f}")
        print(f"  - Answer Relevance: {best_result.answer_relevance:.4f}")
        print(f"  - Context Precision: {best_result.context_precision:.4f}")
        print(f"  - 加权综合分: {best_result.weighted_score:.4f}")

        print("\n性能指标:")
        print(f"  - 评估耗时: {best_result.duration:.2f} 秒")
        print(f"  - 估算显存: {best_result.memory_usage:.2f} GB")

        print("\n" + "=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG 参数自动调优器")
    parser.add_argument("--test-set", default="test_set.json", help="测试集文件路径")
    parser.add_argument("--use-vllm", action="store_true", help="使用本地 vLLM")
    parser.add_argument("--vllm-url", default="http://localhost:8000/v1", help="vLLM 服务地址")
    parser.add_argument("--sample-ratio", type=float, default=1.0, help="参数采样比例 (0.0-1.0)")
    parser.add_argument("--max-workers", type=int, default=3, help="并发线程数")
    parser.add_argument("--early-stop-threshold", type=float, default=0.85, help="早停阈值")
    parser.add_argument("--early-stop-patience", type=int, default=2, help="早停耐心轮数")
    parser.add_argument("--log-file", default="tuning_log.csv", help="日志输出文件")
    parser.add_argument("--config-file", default="best_config.yaml", help="最佳配置输出文件")
    parser.add_argument("--chart-dir", default="charts", help="图表输出目录")

    args = parser.parse_args()

    # 初始化调优器
    tuner = RAGTuner(
        test_set_path=args.test_set,
        use_vllm=args.use_vllm,
        vllm_url=args.vllm_url,
        max_workers=args.max_workers,
        early_stop_threshold=args.early_stop_threshold,
        early_stop_patience=args.early_stop_patience
    )

    # 运行调优
    best_result, all_results = tuner.run_tuning(
        sample_ratio=args.sample_ratio,
        log_file=args.log_file
    )

    # 输出总结
    if best_result:
        tuner.print_summary(best_result, all_results)

        # 导出最佳配置
        tuner.export_best_config(args.config_file)

        # 生成图表
        tuner.generate_charts(all_results, args.chart_dir)


if __name__ == "__main__":
    main()
