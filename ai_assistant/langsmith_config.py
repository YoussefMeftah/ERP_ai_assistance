"""
LangSmith Evaluation Configuration and Advanced Utilities

Provides:
- Configuration management for LangSmith projects
- Advanced evaluation runners (batch, streaming, with retry logic)
- Evaluation result analysis and reporting
"""

import os
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class EvaluationMode(Enum):
    """Evaluation execution modes."""
    SYNC = "sync"
    ASYNC = "async"
    BATCH = "batch"  # Process multiple examples in batches


@dataclass
class LangSmithConfig:
    """Configuration for LangSmith integration."""
    
    # API Configuration
    api_key: Optional[str] = None
    api_url: str = "https://api.smith.langchain.com"
    
    # Project Configuration
    project_name: str = "endpoint_selection_evaluation"
    dataset_name: str = "endpoint_selection_test_cases"
    
    # Evaluation Parameters
    mode: EvaluationMode = EvaluationMode.ASYNC
    batch_size: int = 10
    max_workers: int = 4
    timeout_seconds: int = 300
    
    # Logging
    log_dir: str = "./langsmith_logs"
    verbose: bool = True
    
    def __post_init__(self):
        """Validate and load configuration from environment."""
        if not self.api_key:
            self.api_key = os.getenv("LANGSMITH_API_KEY")
        
        # Create log directory
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["mode"] = self.mode.value
        return data
    
    @classmethod
    def from_env(cls) -> "LangSmithConfig":
        """Load configuration from environment variables."""
        return cls(
            api_key=os.getenv("LANGSMITH_API_KEY"),
            api_url=os.getenv("LANGSMITH_API_URL", "https://api.smith.langchain.com"),
            project_name=os.getenv("LANGSMITH_PROJECT", "endpoint_selection_evaluation"),
            dataset_name=os.getenv("LANGSMITH_DATASET", "endpoint_selection_test_cases"),
            mode=EvaluationMode(os.getenv("LANGSMITH_MODE", "async")),
            batch_size=int(os.getenv("LANGSMITH_BATCH_SIZE", "10")),
            max_workers=int(os.getenv("LANGSMITH_MAX_WORKERS", "4")),
            timeout_seconds=int(os.getenv("LANGSMITH_TIMEOUT", "300")),
            verbose=os.getenv("LANGSMITH_VERBOSE", "true").lower() == "true",
        )


# Default configuration instance
default_config = LangSmithConfig.from_env()


# ============================================================================
# EVALUATION RESULT ANALYSIS
# ============================================================================

class EvaluationResultAnalyzer:
    """Analyze and report on evaluation results."""
    
    @staticmethod
    def aggregate_scores(results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Aggregate scores from multiple evaluation results.
        
        Args:
            results: List of evaluation result dictionaries
            
        Returns:
            Dictionary of aggregated metrics
        """
        if not results:
            return {}
        
        metrics = {}
        
        # Collect all score keys
        all_keys = set()
        for result in results:
            if "scores" in result:
                all_keys.update(result["scores"].keys())
        
        # Aggregate each metric
        for key in all_keys:
            scores = []
            for result in results:
                if "scores" in result:
                    score = result.get("scores", {}).get(key, 0)
                    # Convert to float in case it's a string
                    try:
                        scores.append(float(score))
                    except (ValueError, TypeError):
                        scores.append(0.0)
            
            if scores:
                metrics[key] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores),
                }
        
        return metrics
    
    @staticmethod
    def generate_report(results: List[Dict[str, Any]]) -> str:
        """
        Generate a human-readable evaluation report.
        
        Args:
            results: List of evaluation results
            
        Returns:
            Formatted report string
        """
        metrics = EvaluationResultAnalyzer.aggregate_scores(results)
        
        report = []
        report.append("=" * 70)
        report.append("LangSmith Evaluation Report")
        report.append("=" * 70)
        report.append(f"\nTotal Test Cases: {len(results)}")
        
        # Success rate
        successes = sum(1 for r in results if r.get("success", False))
        report.append(f"Success Rate: {successes}/{len(results)} ({100*successes/len(results):.1f}%)")
        
        # Metric summaries
        report.append("\nMetric Summary:")
        report.append("-" * 70)
        
        for metric_name, stats in metrics.items():
            report.append(f"\n{metric_name}:")
            report.append(f"  Mean:  {stats['mean']:.3f}")
            report.append(f"  Min:   {stats['min']:.3f}")
            report.append(f"  Max:   {stats['max']:.3f}")
            report.append(f"  Count: {stats['count']}")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
    
    @staticmethod
    def identify_failures(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify test cases that failed or scored below threshold.
        
        Args:
            results: List of evaluation results
            
        Returns:
            List of failed/low-scoring results
        """
        failures = []
        
        for result in results:
            # Add if not successful
            if not result.get("success", False):
                failures.append(result)
                continue
            
            # Add if any score is below 0.5
            scores = result.get("scores", {})
            # Convert all scores to float for comparison
            numeric_scores = []
            for score in scores.values():
                try:
                    numeric_scores.append(float(score))
                except (ValueError, TypeError):
                    numeric_scores.append(0.0)
            
            if any(score < 0.5 for score in numeric_scores):
                failures.append(result)
        
        return failures


# ============================================================================
# EVALUATION CACHING
# ============================================================================

class EvaluationCache:
    """Cache evaluation results to avoid recomputation."""
    
    def __init__(self, cache_dir: str = "./langsmith_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, dataset_id: str, run_id: str) -> Path:
        """Get cache file path for a dataset/run combination."""
        filename = f"{dataset_id}_{run_id}.json"
        return self.cache_dir / filename
    
    def load(self, dataset_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """Load cached evaluation results."""
        cache_path = self.get_cache_path(dataset_id, run_id)
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text())
            except Exception:
                return None
        return None
    
    def save(
        self,
        dataset_id: str,
        run_id: str,
        results: Dict[str, Any]
    ) -> None:
        """Save evaluation results to cache."""
        cache_path = self.get_cache_path(dataset_id, run_id)
        cache_path.write_text(json.dumps(results, indent=2, default=str))
    
    def clear(self) -> None:
        """Clear all cached evaluation results."""
        import shutil
        shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# ============================================================================
# BATCH EVALUATION RUNNER
# ============================================================================

class BatchEvaluationRunner:
    """
    Runs evaluations in batches with progress tracking and error recovery.
    """
    
    def __init__(self, config: LangSmithConfig):
        self.config = config
        self.cache = EvaluationCache(config.log_dir)
    
    async def run_batch(
        self,
        examples: List[Dict[str, Any]],
        inference_fn,
        evaluators: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Run batch evaluation with error handling and retries.
        
        Args:
            examples: List of test examples
            inference_fn: Async function to run inference
            evaluators: List of evaluator objects
            
        Returns:
            List of evaluation results
        """
        import asyncio
        
        results = []
        failed = []
        
        for i, example in enumerate(examples, 1):
            try:
                # Run inference
                pred = await self._run_inference_with_retry(
                    inference_fn,
                    example,
                    max_retries=2
                )
                
                # Evaluate
                eval_result = {
                    "example_id": example.get("id"),
                    "input": example.get("inputs"),
                    "expected": example.get("outputs"),
                    "prediction": pred,
                    "scores": {},
                    "success": True,
                }
                
                # Run evaluators
                for evaluator in evaluators:
                    try:
                        score_result = evaluator._evaluate_strings(
                            str(pred),
                            str(example.get("outputs"))
                        )
                        eval_result["scores"].update(score_result)
                    except Exception as e:
                        if self.config.verbose:
                            print(f"  ⚠️  Evaluator {evaluator.__class__.__name__} failed: {e}")
                
                results.append(eval_result)
                
                if self.config.verbose:
                    print(f"  ✓ {i}/{len(examples)}: Evaluated successfully")
                
            except Exception as e:
                failed.append({
                    "example_id": example.get("id"),
                    "error": str(e),
                })
                if self.config.verbose:
                    print(f"  ✗ {i}/{len(examples)}: Failed - {e}")
        
        if self.config.verbose:
            print(f"\n📊 Results: {len(results)}/{len(examples)} successful")
            if failed:
                print(f"❌ Failed: {len(failed)}")
        
        return results
    
    async def _run_inference_with_retry(
        self,
        inference_fn,
        example: Dict[str, Any],
        max_retries: int = 2
    ) -> Any:
        """Run inference with automatic retries on failure."""
        import asyncio
        
        for attempt in range(max_retries + 1):
            try:
                return await inference_fn(example)
            except Exception as e:
                if attempt < max_retries:
                    if self.config.verbose:
                        print(f"    Retry {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(1)
                else:
                    raise


# ============================================================================
# EVALUATION REPORT GENERATOR
# ============================================================================

class EvaluationReportGenerator:
    """Generate comprehensive evaluation reports."""
    
    @staticmethod
    def generate_html_report(
        results: List[Dict[str, Any]],
        output_path: str = "evaluation_report.html"
    ) -> None:
        """
        Generate an HTML report of evaluation results.
        
        Args:
            results: List of evaluation results
            output_path: Path to write HTML file
        """
        analyzer = EvaluationResultAnalyzer()
        metrics = analyzer.aggregate_scores(results)
        
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>LangSmith Evaluation Report</title>",
            "<style>",
            "  body { font-family: Arial, sans-serif; margin: 20px; }",
            "  h1 { color: #333; }",
            "  .metric { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }",
            "  .success { color: green; }",
            "  .failure { color: red; }",
            "  table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "  th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }",
            "  th { background-color: #4CAF50; color: white; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Evaluation Report - {len(results)} Test Cases</h1>",
        ]
        
        # Metrics summary
        html.append("<h2>Metrics Summary</h2>")
        html.append("<table>")
        html.append("<tr><th>Metric</th><th>Mean</th><th>Min</th><th>Max</th></tr>")
        for metric_name, stats in metrics.items():
            html.append(
                f"<tr><td>{metric_name}</td>"
                f"<td>{stats['mean']:.3f}</td>"
                f"<td>{stats['min']:.3f}</td>"
                f"<td>{stats['max']:.3f}</td></tr>"
            )
        html.append("</table>")
        
        # Failures
        failures = analyzer.identify_failures(results)
        if failures:
            html.append("<h2>Failed Cases</h2>")
            html.append(f"<p class='failure'>{len(failures)} test cases failed or scored below 0.5</p>")
            html.append("<ul>")
            for failure in failures[:10]:  # Show first 10
                html.append(f"<li>{failure.get('example_id')}: {failure.get('error', 'Low score')}</li>")
            html.append("</ul>")
        
        html.extend([
            "</body>",
            "</html>"
        ])
        
        Path(output_path).write_text("\n".join(html))
        print(f"✅ Report saved to {output_path}")


if __name__ == "__main__":
    # Test configuration loading
    config = LangSmithConfig.from_env()
    print("LangSmith Configuration:")
    print(json.dumps(config.to_dict(), indent=2))
