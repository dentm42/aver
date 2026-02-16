#!/usr/bin/env python3
"""
benchmark_aver.py - Performance benchmarking for aver knowledge tracking system

Tests the performance limits of the aver system by measuring:
- Search speed as a function of total records and notes
- File access speed based on number of records and notes

The system uses markdown files as source of truth with SQLite for search indexing.
This benchmark helps determine the practical limits for different system configurations.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import statistics


@dataclass
class BenchmarkResult:
    """Results from a single benchmark iteration"""
    iteration: int
    total_records: int
    notes_per_record: int
    total_notes: int
    
    # Search operations (seconds)
    search_list_time: float
    search_query_time: float
    search_view_time: float
    
    # File access operations (seconds)
    file_read_record_time: float
    file_read_notes_time: float
    
    # Calculated metrics
    total_time: float
    records_per_second: float
    notes_per_second: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run"""
    aver_path: str
    starting_records: int
    upper_limit: int
    records_per_iteration: int
    notes_per_record: int
    termination_threshold: float  # 0.30 = 30% increase
    test_dir: Path
    output_file: Optional[Path]
    verbose: bool
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['test_dir'] = str(self.test_dir)
        if self.output_file:
            result['output_file'] = str(self.output_file)
        return result


class AverBenchmark:
    """Benchmark runner for aver system"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: List[BenchmarkResult] = []
        self.current_total_records = 0
        self.record_ids: List[str] = []
        
    def run_aver_command(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        """Run an aver command with timing"""
        cmd = [
            sys.executable,
            self.config.aver_path,
            "--no-use-git-id",
            "--override-repo-boundary",
            "--location", str(self.config.test_dir),
            *args
        ]
        
        if self.config.verbose:
            print(f"Running: {' '.join(cmd)}", file=sys.stderr)
        
        retval = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True
        )

        if self.config.verbose:
            print(f"{retval}", file=sys.stderr)

        return retval
    
    def initialize_database(self):
        """Initialize the aver database"""
        print("Initializing database...")
        self.run_aver_command("admin","init")
    
    def create_records(self, count: int) -> List[str]:
        """Create a batch of records and return their IDs"""
        print(f"Creating {count} records...")
        new_ids = []
        
        for i in range(count):
            # Create record with minimal content
            record_num = self.current_total_records + i + 1
            description = f"Test record {record_num} for benchmarking"
            
            result = self.run_aver_command(
                "record", "new",
                "--title", f"Benchmark Record {record_num}",
                "--kv", f"test_field=value_{record_num}",
                "--description",
                description
            )
            
            # Extract record ID from output
            output = result.stdout.strip()
            # Output format: "Created record: REC-XXXXX"
            if "Created record:" in output:
                record_id = output.split("Created record:")[1].strip()
                record_id = record_id.split("\n")[0].strip()
                new_ids.append(record_id)
        
        self.current_total_records += count
        return new_ids
    
    def create_notes_for_record(self, record_id: str, count: int):
        """Add notes to a specific record"""
        if self.config.verbose:
            print(f"  Adding {count} notes to {record_id}...")
        
        for i in range(count):
            note_content = f"Benchmark note {i+1} for {record_id}"
            self.run_aver_command(
                "note","add",
                record_id,
                "--message",
                note_content
            )
    
    def benchmark_search_operations(self) -> Dict[str, float]:
        """Benchmark various search operations"""
        results = {}
        
        # Test 1: List all records
        start = time.perf_counter()
        self.run_aver_command("record","list")
        results['list_time'] = time.perf_counter() - start
        
        # Test 2: Search query (substring match)
        start = time.perf_counter()
        #self.run_aver_command("search", "Benchmark")
        results['query_time'] = time.perf_counter() - start
        
        # Test 3: View a specific record (includes searching for it)
        if self.record_ids:
            # Use middle record to avoid caching bias
            middle_id = self.record_ids[len(self.record_ids) // 2]
            start = time.perf_counter()
            self.run_aver_command("record","view", middle_id)
            results['view_time'] = time.perf_counter() - start
        else:
            results['view_time'] = 0.0
        
        return results
    
    def benchmark_file_operations(self) -> Dict[str, float]:
        """Benchmark file access operations"""
        results = {}
        
        if not self.record_ids:
            return {'read_record_time': 0.0, 'read_notes_time': 0.0}
        
        # Test 1: Read record file directly
        middle_id = self.record_ids[len(self.record_ids) // 2]
        record_file = self.config.test_dir / "records" / f"{middle_id}.md"
        
        start = time.perf_counter()
        if record_file.exists():
            _ = record_file.read_text()
        results['read_record_time'] = time.perf_counter() - start
        
        # Test 2: Read all notes for a record
        notes_dir = self.config.test_dir / "records" / middle_id
        
        start = time.perf_counter()
        if notes_dir.exists() and notes_dir.is_dir():
            for note_file in notes_dir.glob("*.md"):
                _ = note_file.read_text()
        results['read_notes_time'] = time.perf_counter() - start
        
        return results
    
    def run_iteration(self, iteration: int) -> BenchmarkResult:
        """Run a single benchmark iteration"""
        print(f"\n{'='*70}")
        print(f"Iteration {iteration}")
        print(f"{'='*70}")
        
        # Add new records if not the first iteration
        if iteration > 1:
            new_ids = self.create_records(self.config.records_per_iteration)
            self.record_ids.extend(new_ids)
            
            # Add notes to newly created records
            for record_id in new_ids:
                self.create_notes_for_record(record_id, self.config.notes_per_record)
        else:
            # First iteration: create initial batch
            new_ids = self.create_records(self.config.starting_records)
            self.record_ids.extend(new_ids)
            
            # Add notes to all records
            for record_id in new_ids:
                self.create_notes_for_record(record_id, self.config.notes_per_record)
        
        total_notes = self.current_total_records * self.config.notes_per_record
        
        print(f"\nCurrent state:")
        print(f"  Total records: {self.current_total_records}")
        print(f"  Notes per record: {self.config.notes_per_record}")
        print(f"  Total notes: {total_notes}")
        
        # Run benchmarks
        print("\nBenchmarking search operations...")
        search_results = self.benchmark_search_operations()
        
        print("Benchmarking file operations...")
        file_results = self.benchmark_file_operations()
        
        # Calculate total time and rates
        total_time = sum(search_results.values()) + sum(file_results.values())
        records_per_sec = self.current_total_records / total_time if total_time > 0 else 0
        notes_per_sec = total_notes / total_time if total_time > 0 else 0
        
        result = BenchmarkResult(
            iteration=iteration,
            total_records=self.current_total_records,
            notes_per_record=self.config.notes_per_record,
            total_notes=total_notes,
            search_list_time=search_results['list_time'],
            search_query_time=search_results['query_time'],
            search_view_time=search_results['view_time'],
            file_read_record_time=file_results['read_record_time'],
            file_read_notes_time=file_results['read_notes_time'],
            total_time=total_time,
            records_per_second=records_per_sec,
            notes_per_second=notes_per_sec
        )
        
        # Print results
        print(f"\nResults:")
        print(f"  Search list: {result.search_list_time:.4f}s")
        print(f"  Search query: {result.search_query_time:.4f}s")
        print(f"  Search view: {result.search_view_time:.4f}s")
        print(f"  File read record: {result.file_read_record_time:.4f}s")
        print(f"  File read notes: {result.file_read_notes_time:.4f}s")
        print(f"  Total time: {result.total_time:.4f}s")
        print(f"  Records/sec: {result.records_per_second:.2f}")
        print(f"  Notes/sec: {result.notes_per_second:.2f}")
        
        return result
    
    def check_termination_condition(self) -> bool:
        """Check if we should terminate based on performance degradation"""
        if len(self.results) < 2:
            return False
        
        # Compare last two iterations
        prev_result = self.results[-2]
        curr_result = self.results[-1]
        
        # Calculate percentage increase in total time
        if prev_result.total_time == 0:
            return False
        
        time_increase = (curr_result.total_time - prev_result.total_time) / prev_result.total_time
        
        if time_increase > self.config.termination_threshold:
            print(f"\n{'='*70}")
            print(f"EARLY TERMINATION")
            print(f"{'='*70}")
            print(f"Performance degradation detected:")
            print(f"  Previous iteration time: {prev_result.total_time:.4f}s")
            print(f"  Current iteration time: {curr_result.total_time:.4f}s")
            print(f"  Increase: {time_increase*100:.1f}% (threshold: {self.config.termination_threshold*100:.1f}%)")
            return True
        
        return False
    
    def run_benchmark(self):
        """Run the full benchmark suite"""
        print(f"\n{'='*70}")
        print("AVER PERFORMANCE BENCHMARK")
        print(f"{'='*70}")
        print(f"\nConfiguration:")
        print(f"  Starting records: {self.config.starting_records}")
        print(f"  Upper limit: {self.config.upper_limit}")
        print(f"  Records per iteration: {self.config.records_per_iteration}")
        print(f"  Notes per record: {self.config.notes_per_record}")
        print(f"  Termination threshold: {self.config.termination_threshold*100:.1f}%")
        print(f"  Test directory: {self.config.test_dir}")
        
        # Initialize
        self.initialize_database()
        
        # Run iterations
        iteration = 1
        while self.current_total_records < self.config.upper_limit:
            result = self.run_iteration(iteration)
            self.results.append(result)
            
            # Check for early termination
            if self.check_termination_condition():
                break
            
            # Check if we've reached the limit
            if self.current_total_records >= self.config.upper_limit:
                print(f"\nReached upper limit of {self.config.upper_limit} records")
                break
            
            iteration += 1
        
        # Print summary
        self.print_summary()
        
        # Save results if output file specified
        if self.config.output_file:
            self.save_results()
    
    def print_summary(self):
        """Print benchmark summary"""
        if not self.results:
            print("\nNo results to summarize")
            return
        
        print(f"\n{'='*70}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*70}")
        
        print(f"\nIterations completed: {len(self.results)}")
        print(f"Final record count: {self.results[-1].total_records}")
        print(f"Final note count: {self.results[-1].total_notes}")
        
        # Calculate statistics for each metric
        metrics = {
            'search_list_time': [r.search_list_time for r in self.results],
            'search_query_time': [r.search_query_time for r in self.results],
            'search_view_time': [r.search_view_time for r in self.results],
            'file_read_record_time': [r.file_read_record_time for r in self.results],
            'file_read_notes_time': [r.file_read_notes_time for r in self.results],
            'total_time': [r.total_time for r in self.results],
        }
        
        print("\nPerformance statistics across all iterations:")
        print(f"{'Metric':<25} {'Min':<10} {'Max':<10} {'Avg':<10} {'Median':<10}")
        print("-" * 70)
        
        for metric_name, values in metrics.items():
            if values:
                min_val = min(values)
                max_val = max(values)
                avg_val = statistics.mean(values)
                med_val = statistics.median(values)
                
                display_name = metric_name.replace('_', ' ').title()
                print(f"{display_name:<25} {min_val:<10.4f} {max_val:<10.4f} {avg_val:<10.4f} {med_val:<10.4f}")
        
        # Performance degradation analysis
        if len(self.results) >= 2:
            print("\nPerformance trend (first vs. last iteration):")
            first = self.results[0]
            last = self.results[-1]
            
            print(f"  Records: {first.total_records} -> {last.total_records} "
                  f"({(last.total_records/first.total_records - 1)*100:+.1f}%)")
            print(f"  Total time: {first.total_time:.4f}s -> {last.total_time:.4f}s "
                  f"({(last.total_time/first.total_time - 1)*100:+.1f}%)")
            
            if first.total_time > 0:
                time_per_record_first = first.total_time / first.total_records
                time_per_record_last = last.total_time / last.total_records
                print(f"  Time per record: {time_per_record_first:.6f}s -> {time_per_record_last:.6f}s "
                      f"({(time_per_record_last/time_per_record_first - 1)*100:+.1f}%)")
        
        # Recommendations
        print("\nRecommendations:")
        last_result = self.results[-1]
        
        if last_result.total_time < 1.0:
            print("  ✓ System performs well at this scale")
            print(f"  ✓ Can likely handle {last_result.total_records * 2}+ records")
        elif last_result.total_time < 5.0:
            print("  ⚠ System performance is acceptable but slowing")
            print(f"  ⚠ Consider {last_result.total_records} records as soft limit")
        else:
            print("  ✗ System performance is degraded")
            print(f"  ✗ Recommended limit: {last_result.total_records // 2} records")
    
    def save_results(self):
        """Save benchmark results to JSON file"""
        output_data = {
            'config': self.config.to_dict(),
            'results': [r.to_dict() for r in self.results],
            'summary': {
                'iterations': len(self.results),
                'final_records': self.results[-1].total_records if self.results else 0,
                'final_notes': self.results[-1].total_notes if self.results else 0,
            }
        }
        
        with open(self.config.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to: {self.config.output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark aver.py performance limits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic benchmark with 10,000 record limit
  %(prog)s --upper-limit 10000

  # Start with 1000 records, test up to 50,000
  %(prog)s --starting-records 1000 --upper-limit 50000

  # Quick test with aggressive termination
  %(prog)s --upper-limit 5000 --threshold 0.20

  # Full benchmark with custom notes per record
  %(prog)s --upper-limit 20000 --notes-per-record 10 --output benchmark_results.json

The benchmark will:
1. Create records incrementally (default: 100 per iteration)
2. Add notes to each record (default: 5 per record)
3. Measure search and file access performance
4. Terminate early if performance degrades >30% between iterations
5. Provide recommendations based on results
        """
    )
    
    parser.add_argument(
        "--aver-path",
        default="./aver.py",
        help="Path to aver.py script (default: ./aver.py)"
    )
    
    parser.add_argument(
        "--starting-records",
        type=int,
        default=100,
        help="Number of records to start with (default: 100)"
    )
    
    parser.add_argument(
        "--upper-limit",
        type=int,
        required=True,
        help="Maximum number of records to test (required)"
    )
    
    parser.add_argument(
        "--records-per-iteration",
        type=int,
        default=100,
        help="Number of records to add per iteration (default: 100)"
    )
    
    parser.add_argument(
        "--notes-per-record",
        type=int,
        default=5,
        help="Number of notes to add to each record (default: 5)"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.30,
        help="Early termination threshold as decimal (default: 0.30 = 30%% increase)"
    )
    
    parser.add_argument(
        "--test-dir",
        type=Path,
        help="Directory for test data (default: temporary directory)"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for benchmark results (JSON)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.starting_records > args.upper_limit:
        parser.error("--starting-records must be less than --upper-limit")
    
    if args.threshold <= 0 or args.threshold > 1:
        parser.error("--threshold must be between 0 and 1")
    
    # Find aver.py
    aver_path = Path(args.aver_path)
    if not aver_path.exists():
        print(f"Error: Cannot find aver.py at {aver_path}", file=sys.stderr)
        sys.exit(1)
    
    # Create test directory
    if args.test_dir:
        test_dir = args.test_dir
        test_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        test_dir = Path(tempfile.mkdtemp(prefix="aver-benchmark-"))
        cleanup = True
    
    try:
        # Create config
        config = BenchmarkConfig(
            aver_path=str(aver_path.absolute()),
            starting_records=args.starting_records,
            upper_limit=args.upper_limit,
            records_per_iteration=args.records_per_iteration,
            notes_per_record=args.notes_per_record,
            termination_threshold=args.threshold,
            test_dir=test_dir,
            output_file=args.output,
            verbose=args.verbose
        )
        
        # Run benchmark
        benchmark = AverBenchmark(config)
        benchmark.run_benchmark()
        
    finally:
        # Cleanup if using temporary directory
        if cleanup and test_dir.exists():
            print(f"\nCleaning up test directory: {test_dir}")
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    main()
