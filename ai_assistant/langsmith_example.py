#!/usr/bin/env python3
"""
LangSmith Evaluation - Complete Example and Runner

This script demonstrates how to use the LangSmith evaluation system.

Examples:

  # 1. Create dataset only
  python langsmith_example.py --dataset-only
  
  # 2. Run quick evaluation (first 3 examples)
  python langsmith_example.py --quick
  
  # 3. Full evaluation with batch processing
  python langsmith_example.py --full
  
  # 4. Generate HTML report
  python langsmith_example.py --full --report
  
  # 5. Clear cache and re-evaluate
  python langsmith_example.py --clear-cache --full
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from langsmith_config import (
    LangSmithConfig,
    EvaluationResultAnalyzer,
    BatchEvaluationRunner,
    EvaluationReportGenerator,
)
from langsmith_evaluation import (
    create_or_update_dataset,
    build_evaluation_graph,
    run_test_case_async,
    EndpointExactMatchEvaluator,
    ParameterExtractionEvaluator,
    IntentClassificationEvaluator,
    DomainClassificationEvaluator,
    DATASET_NAME,
    TEST_CASES,
)


class EvaluationRunner:
    """High-level runner for LangSmith evaluations."""
    
    def __init__(self, config: LangSmithConfig):
        self.config = config
        self.batch_runner = BatchEvaluationRunner(config)
        self.analyzer = EvaluationResultAnalyzer()
    
    async def run_quick_eval(self, limit: int = 3):
        """Run evaluation on first N examples."""
        print(f"\n⚡ Quick Evaluation (first {limit} examples)")
        print("=" * 70)
        
        return await self._run_evaluation(limit)
    
    async def run_full_eval(self):
        """Run evaluation on all test cases."""
        print("\n🚀 Full Evaluation (all test cases)")
        print("=" * 70)
        
        return await self._run_evaluation(len(TEST_CASES))
    
    async def _run_evaluation(self, limit: int):
        """Internal evaluation runner."""
        # Build graph
        print("\n📦 Building evaluation graph...")
        graph = build_evaluation_graph()
        
        # Create test examples
        examples = TEST_CASES[:limit]
        print(f"📊 Loaded {len(examples)} test cases")
        
        # Create evaluators
        evaluators = [
            EndpointExactMatchEvaluator(),
            ParameterExtractionEvaluator(),
            IntentClassificationEvaluator(),
            DomainClassificationEvaluator(),
        ]
        print(f"📋 Configured {len(evaluators)} evaluators")
        
        # Prepare inference function
        async def inference_fn(example):
            question = example.get("input", {}).get("question", "")
            return await run_test_case_async(question, graph)
        
        # Run batch evaluation
        print(f"\n⏳ Running inference and evaluation...")
        results = await self.batch_runner.run_batch(
            examples,
            inference_fn,
            evaluators,
        )
        
        # Print results
        print(f"\n📊 Evaluation Complete!")
        print("=" * 70)
        
        # Aggregate and display metrics
        metrics = self.analyzer.aggregate_scores(results)
        
        print("\n✅ Metrics:")
        for metric_name, stats in metrics.items():
            print(f"\n  {metric_name}:")
            print(f"    Mean:  {stats['mean']:.3f}")
            print(f"    Min:   {stats['min']:.3f}")
            print(f"    Max:   {stats['max']:.3f}")
        
        # Identify failures
        failures = self.analyzer.identify_failures(results)
        if failures:
            print(f"\n⚠️  Failed/Low-scoring cases: {len(failures)}")
            for failure in failures[:5]:
                print(f"  - {failure.get('example_id', 'unknown')}: {failure.get('error', 'Low score')}")
        
        return results
    
    async def generate_report(self, results: List[Dict[str, Any]]):
        """Generate HTML report from results."""
        print("\n📄 Generating HTML report...")
        report_path = Path(self.config.log_dir) / "evaluation_report.html"
        EvaluationReportGenerator.generate_html_report(results, str(report_path))


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="LangSmith Evaluation Runner"
    )
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        help="Only create/update dataset",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick evaluation (first 3 examples)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full evaluation (all examples)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear evaluation cache before running",
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = LangSmithConfig.from_env()
    
    if not config.api_key:
        print("❌ Error: LANGSMITH_API_KEY not set")
        print("   Set it with: $env:LANGSMITH_API_KEY='your_api_key'")
        return 1
    
    print("🔐 LangSmith Configuration:")
    print(f"  Project: {config.project_name}")
    print(f"  Dataset: {config.dataset_name}")
    print(f"  Mode: {config.mode.value}")
    
    # Create dataset
    print("\n📊 Creating/updating dataset...")
    try:
        dataset_name = create_or_update_dataset()
        print(f"✅ Dataset ready: {dataset_name}")
    except Exception as e:
        print(f"❌ Failed to create dataset: {e}")
        return 1
    
    # Run evaluations
    runner = EvaluationRunner(config)
    results = None
    
    if args.clear_cache:
        runner.batch_runner.cache.clear()
        print("✅ Cache cleared")
    
    if args.quick:
        results = await runner.run_quick_eval()
    elif args.full:
        results = await runner.run_full_eval()
    elif not args.dataset_only:
        # Default: quick eval
        results = await runner.run_quick_eval()
    
    # Generate report if requested
    if args.report and results:
        await runner.generate_report(results)
    
    print("\n✅ Done!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
