#!/usr/bin/env python3
"""RAGAS 一键评估脚本 - 自动评估 RAG 系统性能"""

import json
import os
import sqlite3
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
import statistics

import openai
from openai import OpenAI, AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@dataclass
class TestSample:
    """测试样本数据结构"""
    question: str
    answer: str
    context: List[str]
    id: Optional[int] = None


@dataclass
class EvaluationResult:
    """单样本评估结果"""
    sample_id: int
    question: str
    answer: str
    context: List[str]
    faithfulness: float
    answer_relevance: float
    context_precision: float
    timestamp: str


@dataclass
class ReportSummary:
    """评估报告摘要"""
    total_samples: int
    avg_faithfulness: float
    avg_answer_relevance: float
    avg_context_precision: float
    score_distribution: Dict[str, int]
    low_score_samples: List[Dict[str, Any]]
    suggestions: List[str]


class SQLiteStorage:
    """SQLite 存储管理类"""

    def __init__(self, db_path: str = "ragas_evaluation.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                total_samples INTEGER NOT NULL,
                avg_faithfulness REAL,
                avg_answer_relevance REAL,
                avg_context_precision REAL,
                score_distribution TEXT,
                low_score_samples TEXT,
                suggestions TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sample_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER,
                sample_id INTEGER,
                question TEXT,
                answer TEXT,
                context TEXT,
                faithfulness REAL,
                answer_relevance REAL,
                context_precision REAL,
                FOREIGN KEY (evaluation_id) REFERENCES evaluations(id)
            )
        ''')

        conn.commit()
        conn.close()

    def save_evaluation(self, summary: ReportSummary, results: List[EvaluationResult], version: str = "1.0"):
        """保存评估结果到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO evaluations (
                version, timestamp, total_samples, avg_faithfulness,
                avg_answer_relevance, avg_context_precision,
                score_distribution, low_score_samples, suggestions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            version,
            datetime.now().isoformat(),
            summary.total_samples,
            summary.avg_faithfulness,
            summary.avg_answer_relevance,
            summary.avg_context_precision,
            json.dumps(summary.score_distribution),
            json.dumps(summary.low_score_samples),
            json.dumps(summary.suggestions)
        ))

        evaluation_id = cursor.lastrowid

        for result in results:
            cursor.execute('''
                INSERT INTO sample_results (
                    evaluation_id, sample_id, question, answer, context,
                    faithfulness, answer_relevance, context_precision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                evaluation_id,
                result.sample_id,
                result.question,
                result.answer,
                json.dumps(result.context),
                result.faithfulness,
                result.answer_relevance,
                result.context_precision
            ))

        conn.commit()
        conn.close()
        print(f"评估结果已保存到数据库，版本: {version}")

    def get_history_versions(self) -> List[Dict[str, Any]]:
        """获取历史版本列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, version, timestamp, avg_faithfulness,
                   avg_answer_relevance, avg_context_precision
            FROM evaluations ORDER BY timestamp DESC
        ''')

        versions = []
        for row in cursor.fetchall():
            versions.append({
                "id": row[0],
                "version": row[1],
                "timestamp": row[2],
                "avg_faithfulness": row[3],
                "avg_answer_relevance": row[4],
                "avg_context_precision": row[5]
            })

        conn.close()
        return versions


class RateLimitedLLM:
    """支持速率限制自动重试的 LLM 客户端"""

    def __init__(self, use_vllm: bool = False, vllm_url: str = "http://localhost:8000/v1"):
        self.use_vllm = use_vllm
        self.vllm_url = vllm_url
        self.client = self._init_client()

    def _init_client(self):
        """初始化客户端"""
        if self.use_vllm:
            return OpenAI(base_url=self.vllm_url, api_key="EMPTY")
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
            base_url = os.environ.get("OPENAI_BASE_URL")
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url)
            return OpenAI(api_key=api_key)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.InternalServerError
        ))
    )
    def generate(self, prompt: str, model: str = "gpt-3.5-turbo") -> str:
        """生成响应，支持自动重试"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM 调用失败，正在重试: {str(e)}")
            raise


class RAGASEvaluator:
    """RAGAS 评估器"""

    def __init__(self, llm: RateLimitedLLM):
        self.llm = llm

    def _generate_faithfulness_prompt(self, answer: str, context: List[str]) -> str:
        """生成忠实性评估提示"""
        context_str = "\n".join([f"- {c}" for c in context])
        return f"""
你是一个评估助手。请评估以下回答的忠实性（faithfulness），即回答是否完全基于提供的上下文信息。

上下文:
{context_str}

回答:
{answer}

请根据以下标准评分（0-5分）：
- 5分：回答完全忠实于上下文，没有添加任何外部信息
- 4分：回答基本忠实，仅有微小的未在上下文中明确提及的信息
- 3分：回答大部分忠实，但有少量明显不在上下文中的信息
- 2分：回答部分忠实，存在较多不准确或未提及的信息
- 1分：回答很少忠实于上下文，大部分信息不准确
- 0分：回答完全不忠实于上下文

请仅返回数字评分，不要添加其他解释。
"""

    def _generate_relevance_prompt(self, question: str, answer: str) -> str:
        """生成答案相关性评估提示"""
        return f"""
你是一个评估助手。请评估以下回答与问题的相关性（answer_relevance）。

问题:
{question}

回答:
{answer}

请根据以下标准评分（0-5分）：
- 5分：回答完全相关，准确回答了问题的所有方面
- 4分：回答大部分相关，基本回答了问题的核心
- 3分：回答部分相关，但遗漏了重要信息
- 2分：回答相关性较低，只涉及问题的边缘方面
- 1分：回答很少相关，几乎没有回答问题
- 0分：回答完全不相关

请仅返回数字评分，不要添加其他解释。
"""

    def _generate_precision_prompt(self, question: str, context: List[str]) -> str:
        """生成上下文精确性评估提示"""
        context_str = "\n".join([f"- {c}" for c in context])
        return f"""
你是一个评估助手。请评估上下文的精确性（context_precision），即提供的上下文中有多少比例是回答问题所必需的。

问题:
{question}

上下文:
{context_str}

请根据以下标准评分（0-5分）：
- 5分：所有上下文都与问题高度相关，没有冗余信息
- 4分：大部分上下文相关，仅有少量冗余
- 3分：约一半上下文相关，存在一些冗余
- 2分：较少上下文相关，存在较多冗余
- 1分：很少上下文相关，大部分是冗余信息
- 0分：所有上下文都与问题无关

请仅返回数字评分，不要添加其他解释。
"""

    def evaluate_sample(self, sample: TestSample) -> EvaluationResult:
        """评估单个样本"""
        print(f"正在评估样本 {sample.id}...")

        # 评估忠实性
        faithfulness_prompt = self._generate_faithfulness_prompt(sample.answer, sample.context)
        faithfulness_raw = self.llm.generate(faithfulness_prompt)
        faithfulness = float(faithfulness_raw) / 5.0

        # 评估答案相关性
        relevance_prompt = self._generate_relevance_prompt(sample.question, sample.answer)
        relevance_raw = self.llm.generate(relevance_prompt)
        answer_relevance = float(relevance_raw) / 5.0

        # 评估上下文精确性
        precision_prompt = self._generate_precision_prompt(sample.question, sample.context)
        precision_raw = self.llm.generate(precision_prompt)
        context_precision = float(precision_raw) / 5.0

        return EvaluationResult(
            sample_id=sample.id,
            question=sample.question,
            answer=sample.answer,
            context=sample.context,
            faithfulness=faithfulness,
            answer_relevance=answer_relevance,
            context_precision=context_precision,
            timestamp=datetime.now().isoformat()
        )


def load_test_set(file_path: str) -> List[TestSample]:
    """从 JSON 文件加载测试集"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for i, item in enumerate(data, 1):
        samples.append(TestSample(
            id=i,
            question=item["question"],
            answer=item["answer"],
            context=item["context"]
        ))

    return samples


def generate_report(results: List[EvaluationResult]) -> ReportSummary:
    """生成评估报告"""
    if not results:
        return ReportSummary(
            total_samples=0,
            avg_faithfulness=0.0,
            avg_answer_relevance=0.0,
            avg_context_precision=0.0,
            score_distribution={},
            low_score_samples=[],
            suggestions=[]
        )

    # 计算平均分
    faithfulness_scores = [r.faithfulness for r in results]
    relevance_scores = [r.answer_relevance for r in results]
    precision_scores = [r.context_precision for r in results]

    avg_faithfulness = statistics.mean(faithfulness_scores)
    avg_answer_relevance = statistics.mean(relevance_scores)
    avg_context_precision = statistics.mean(precision_scores)

    # 计算分数分布
    score_distribution = defaultdict(int)
    for result in results:
        overall = (result.faithfulness + result.answer_relevance + result.context_precision) / 3
        if overall >= 0.8:
            score_distribution["优秀 (≥0.8)"] += 1
        elif overall >= 0.6:
            score_distribution["良好 (0.6-0.79)"] += 1
        elif overall >= 0.4:
            score_distribution["中等 (0.4-0.59)"] += 1
        else:
            score_distribution["较差 (<0.4)"] += 1

    # 识别低分样本
    low_score_samples = []
    for result in results:
        overall = (result.faithfulness + result.answer_relevance + result.context_precision) / 3
        if overall < 0.5:
            low_score_samples.append({
                "sample_id": result.sample_id,
                "question": result.question,
                "answer": result.answer,
                "faithfulness": result.faithfulness,
                "answer_relevance": result.answer_relevance,
                "context_precision": result.context_precision,
                "overall": overall
            })

    # 生成改进建议
    suggestions = []
    if avg_faithfulness < 0.6:
        suggestions.append("【忠实性问题】建议检查回答生成逻辑，确保所有回答都基于提供的上下文，避免幻觉。")
    if avg_answer_relevance < 0.6:
        suggestions.append("【相关性问题】建议优化回答生成的指令，确保回答直接针对问题。")
    if avg_context_precision < 0.6:
        suggestions.append("【精确性问题】建议优化检索策略，减少无关上下文的返回。")
    if len(low_score_samples) > len(results) * 0.3:
        suggestions.append("【整体性能】超过30%的样本表现较差，建议系统性地检查 RAG 流程各环节。")
    if avg_faithfulness >= 0.8 and avg_answer_relevance >= 0.8 and avg_context_precision >= 0.8:
        suggestions.append("【优秀表现】所有指标均表现优秀，继续保持当前配置。")

    return ReportSummary(
        total_samples=len(results),
        avg_faithfulness=avg_faithfulness,
        avg_answer_relevance=avg_answer_relevance,
        avg_context_precision=avg_context_precision,
        score_distribution=dict(score_distribution),
        low_score_samples=low_score_samples,
        suggestions=suggestions
    )


def print_report(report: ReportSummary):
    """打印评估报告"""
    print("\n" + "=" * 60)
    print("RAGAS 评估报告")
    print("=" * 60)

    print(f"\n评估样本数: {report.total_samples}")
    print(f"\n平均指标得分:")
    print(f"  - 忠实性 (Faithfulness): {report.avg_faithfulness:.4f}")
    print(f"  - 答案相关性 (Answer Relevance): {report.avg_answer_relevance:.4f}")
    print(f"  - 上下文精确性 (Context Precision): {report.avg_context_precision:.4f}")

    print(f"\n分数分布:")
    for category, count in report.score_distribution.items():
        percentage = (count / report.total_samples) * 100
        print(f"  - {category}: {count} 个 ({percentage:.1f}%)")

    if report.low_score_samples:
        print(f"\n低分样本溯源 (分数 < 0.5):")
        for sample in report.low_score_samples[:5]:
            print(f"\n  样本 {sample['sample_id']}:")
            print(f"    问题: {sample['question'][:50]}...")
            print(f"    忠实性: {sample['faithfulness']:.4f}")
            print(f"    相关性: {sample['answer_relevance']:.4f}")
            print(f"    精确性: {sample['context_precision']:.4f}")
            print(f"    综合得分: {sample['overall']:.4f}")

    if report.suggestions:
        print(f"\n改进建议:")
        for i, suggestion in enumerate(report.suggestions, 1):
            print(f"  {i}. {suggestion}")

    print("\n" + "=" * 60)


def compare_versions(storage: SQLiteStorage, version1_id: int, version2_id: int):
    """对比两个版本的评估结果"""
    conn = sqlite3.connect(storage.db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT version, timestamp, avg_faithfulness,
               avg_answer_relevance, avg_context_precision
        FROM evaluations WHERE id IN (?, ?)
    ''', (version1_id, version2_id))

    rows = cursor.fetchall()
    if len(rows) != 2:
        print("无法找到指定版本")
        return

    v1, v2 = rows[0], rows[1]

    print("\n" + "=" * 60)
    print(f"版本对比: {v1[0]} vs {v2[0]}")
    print("=" * 60)

    print(f"\n版本 {v1[0]} ({v1[1]}):")
    print(f"  忠实性: {v1[2]:.4f}")
    print(f"  相关性: {v1[3]:.4f}")
    print(f"  精确性: {v1[4]:.4f}")

    print(f"\n版本 {v2[0]} ({v2[1]}):")
    print(f"  忠实性: {v2[2]:.4f}")
    print(f"  相关性: {v2[3]:.4f}")
    print(f"  精确性: {v2[4]:.4f}")

    print(f"\n变化趋势:")
    print(f"  忠实性: {'↑' if v2[2] > v1[2] else '↓' if v2[2] < v1[2] else '→'} "
          f"{abs(v2[2] - v1[2]):.4f}")
    print(f"  相关性: {'↑' if v2[3] > v1[3] else '↓' if v2[3] < v1[3] else '→'} "
          f"{abs(v2[3] - v1[3]):.4f}")
    print(f"  精确性: {'↑' if v2[4] > v1[4] else '↓' if v2[4] < v1[4] else '→'} "
          f"{abs(v2[4] - v1[4]):.4f}")

    conn.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="RAGAS 一键评估脚本")
    parser.add_argument("--test-set", default="test_set.json", help="测试集文件路径")
    parser.add_argument("--use-vllm", action="store_true", help="使用本地 vLLM")
    parser.add_argument("--vllm-url", default="http://localhost:8000/v1", help="vLLM 服务地址")
    parser.add_argument("--version", default="1.0", help="评估版本号")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="LLM 模型名称")
    parser.add_argument("--compare", nargs=2, type=int, help="对比两个版本 (version_id1 version_id2)")
    args = parser.parse_args()

    storage = SQLiteStorage()

    # 对比模式
    if args.compare:
        compare_versions(storage, args.compare[0], args.compare[1])
        return

    # 检查测试集文件
    if not os.path.exists(args.test_set):
        print(f"测试集文件不存在: {args.test_set}")
        print("正在生成示例测试集...")
        generate_example_test_set(args.test_set)

    # 加载测试集
    print(f"加载测试集: {args.test_set}")
    samples = load_test_set(args.test_set)
    print(f"共加载 {len(samples)} 个测试样本")

    # 初始化 LLM
    llm = RateLimitedLLM(use_vllm=args.use_vllm, vllm_url=args.vllm_url)

    # 初始化评估器
    evaluator = RAGASEvaluator(llm)

    # 执行评估
    print("\n开始评估...")
    results = []
    for sample in samples:
        result = evaluator.evaluate_sample(sample)
        results.append(result)
        print(f"  样本 {sample.id}: F={result.faithfulness:.4f}, R={result.answer_relevance:.4f}, P={result.context_precision:.4f}")

    # 生成报告
    report = generate_report(results)

    # 打印报告
    print_report(report)

    # 保存结果
    storage.save_evaluation(report, results, args.version)

    # 显示历史版本
    print("\n历史版本记录:")
    versions = storage.get_history_versions()
    for v in versions[:5]:
        print(f"  ID:{v['id']} 版本:{v['version']} 时间:{v['timestamp'][:19]} "
              f"F={v['avg_faithfulness']:.4f} R={v['avg_answer_relevance']:.4f} P={v['avg_context_precision']:.4f}")


def generate_example_test_set(file_path: str):
    """生成示例测试集"""
    example_data = [
        {
            "question": "什么是 RAG 技术？",
            "answer": "RAG（Retrieval-Augmented Generation）是一种结合检索和生成的人工智能技术，通过从外部知识库检索相关信息来增强生成模型的回答能力。",
            "context": [
                "RAG 即 Retrieval-Augmented Generation，是一种检索增强生成技术。",
                "RAG 结合了信息检索和大型语言模型的生成能力。",
                "通过检索外部知识库，可以为生成模型提供最新、准确的信息。"
            ]
        },
        {
            "question": "LangChain 是什么？",
            "answer": "LangChain 是一个用于构建基于语言模型的应用程序的框架，提供了工具和组件来连接各种 AI 服务和数据源。",
            "context": [
                "LangChain 是一个开源框架，用于开发由语言模型驱动的应用程序。",
                "它提供了与多种 LLM 提供商的集成，包括 OpenAI、Anthropic 等。",
                "LangChain 支持文档加载、分割、检索和生成等功能。"
            ]
        },
        {
            "question": "向量数据库的主要用途是什么？",
            "answer": "向量数据库主要用于存储和检索高维向量数据，广泛应用于语义搜索、推荐系统和 AI 应用中。",
            "context": [
                "向量数据库是专门设计用于存储和查询向量嵌入的数据库。",
                "它们支持高效的相似度搜索，用于找到与查询向量最相似的向量。",
                "常见的向量数据库包括 Pinecone、Chroma、FAISS 等。",
                "天气很好，适合户外活动。"
            ]
        },
        {
            "question": "如何优化 RAG 系统的性能？",
            "answer": "可以通过优化检索策略、使用更好的嵌入模型、调整 chunk 大小等方法来优化 RAG 系统的性能。",
            "context": [
                "优化 RAG 系统的方法包括改进检索算法和使用更精确的嵌入模型。",
                "调整文档分割策略可以提高检索的准确性。",
                "使用混合检索方法可以结合关键词和语义搜索的优点。"
            ]
        },
        {
            "question": "什么是提示词工程？",
            "answer": "提示词工程是设计和优化提示词以获得更好的 AI 模型输出的过程，包括指令设计、上下文管理和格式规范等方面。",
            "context": [
                "提示词工程是指设计有效的提示来引导 AI 模型生成期望的输出。",
                "良好的提示词可以提高模型回答的准确性和相关性。",
                "提示词工程包括明确的指令、示例和上下文管理。"
            ]
        }
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(example_data, f, ensure_ascii=False, indent=2)

    print(f"示例测试集已生成: {file_path}")


if __name__ == "__main__":
    main()
