#!/usr/bin/env python3
"""
benchmark_aver.py - Performance benchmarking for aver knowledge tracking system

Tests the performance limits of the aver system by measuring:
- Search speed as a function of total records and notes
- File access speed based on number of records and notes

The system uses markdown files as source of truth with SQLite for search indexing.
This benchmark helps determine the practical limits for different system configurations.

Now uses JSON IO interface for much faster data injection.
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
    """Benchmark runner for aver system using JSON IO interface"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: List[BenchmarkResult] = []
        self.current_total_records = 0
        self.record_ids: List[str] = []
        self.io_process: Optional[subprocess.Popen] = None
        
    def start_json_io(self):
        """Start the JSON IO interface as a persistent process"""
        cmd = [
            sys.executable,
            self.config.aver_path,
            "--no-use-git-id",
            "--override-repo-boundary",
            "--location", str(self.config.test_dir),
            "json", "io"
        ]
        
        if self.config.verbose:
            print(f"Starting JSON IO: {' '.join(cmd)}", file=sys.stderr)
        
        self.io_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
    def stop_json_io(self):
        """Stop the JSON IO process"""
        if self.io_process:
            self.io_process.stdin.close()
            self.io_process.wait()
            self.io_process = None
    
    def send_json_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the JSON IO interface and get response"""
        if not self.io_process:
            raise RuntimeError("JSON IO process not started")
        
        request = {
            "command": command,
            "params": params
        }
        
        if self.config.verbose:
            print(f"Sending: {json.dumps(request)}", file=sys.stderr)
        
        # Send command
        self.io_process.stdin.write(json.dumps(request) + "\n")
        self.io_process.stdin.flush()
        
        # Read response
        response_line = self.io_process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from JSON IO")
        
        response = json.loads(response_line)
        
        if self.config.verbose:
            print(f"Response: {json.dumps(response)}", file=sys.stderr)
        
        if not response.get('success'):
            raise RuntimeError(f"Command failed: {response.get('error', 'Unknown error')}")
        
        return response.get('result', {})
    
    def run_aver_command(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        """Run an aver command directly (for non-IO operations like list/view)"""
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
        self.run_aver_command("admin", "init")
    
    def create_records(self, count: int) -> List[str]:
        """Create a batch of records using JSON IO and return their IDs"""
        print(f"Creating {count} records via JSON IO...")
        new_ids = []
        
        start_time = time.perf_counter()
        
        for i in range(count):
            # Create record with minimal content
            record_num = self.current_total_records + i + 1
            description = f"Test record {record_num} for benchmarking"
            
            result = self.send_json_command(
                "import-record",
                {
                    "content": description,
                    "fields": {
                        "title": f"Benchmark Record {record_num}",
                        "test_field": f"value_{record_num}"
                    }
                }
            )
            
            record_id = result.get('record_id')
            if record_id:
                new_ids.append(record_id)
        
        elapsed = time.perf_counter() - start_time
        if self.config.verbose:
            print(f"  Created {count} records in {elapsed:.2f}s ({count/elapsed:.1f} records/sec)", file=sys.stderr)
        
        self.current_total_records += count
        return new_ids
    
    def create_notes_for_record(self, record_id: str, count: int):
        """Add notes to a specific record using JSON IO"""
        if self.config.verbose:
            print(f"  Adding {count} notes to {record_id}...")
        
        start_time = time.perf_counter()
        
        for i in range(count):
            note_content = f"Benchmark note {i+1} for {record_id}"
            self.send_json_command(
                "import-note",
                {
                    "record_id": record_id,
                    "content": note_content,
                    "fields": {}
                }
            )
        
        if self.config.verbose:
            elapsed = time.perf_counter() - start_time
            print(f"    Added {count} notes in {elapsed:.2f}s ({count/elapsed:.1f} notes/sec)", file=sys.stderr)
    
    def benchmark_search_operations(self) -> Dict[str, float]:
        """Benchmark various search operations"""
        results = {}
        
        # Test 1: List all records
        start = time.perf_counter()
        self.run_aver_command("record", "list")
        results['list_time'] = time.perf_counter() - start
        
        # Test 2: Search query (using JSON IO for consistency)
        start = time.perf_counter()
        # Search for records via JSON IO
        self.send_json_command("search-records", {"limit": 100})
        results['query_time'] = time.perf_counter() - start
        
        # Test 3: View a specific record
        if self.record_ids:
            # Use middle record to avoid caching bias
            middle_id = self.record_ids[len(self.record_ids) // 2]
            start = time.perf_counter()
            self.run_aver_command("record", "view", middle_id)
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
        notes_dir = self.config.test_dir / "updates" / middle_id
        
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
        
        iteration_start = time.perf_counter()
        
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
        print(f"  Records: {self.current_total_records}")
        print(f"  Notes: {total_notes}")
        
        # Run benchmarks
        print("\nBenchmarking search operations...")
        search_results = self.benchmark_search_operations()
        
        print("Benchmarking file operations...")
        file_results = self.benchmark_file_operations()
        
        # Calculate metrics
        total_time = time.perf_counter() - iteration_start
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
        
        # Print iteration results
        print(f"\nIteration {iteration} Results:")
        print(f"  Total time: {total_time:.4f}s")
        print(f"  Records/sec: {records_per_sec:.2f}")
        print(f"  Notes/sec: {notes_per_sec:.2f}")
        print(f"\nSearch operations:")
        print(f"  List all: {search_results['list_time']:.4f}s")
        print(f"  Query: {search_results['query_time']:.4f}s")
        print(f"  View record: {search_results['view_time']:.4f}s")
        print(f"\nFile operations:")
        print(f"  Read record: {file_results['read_record_time']:.4f}s")
        print(f"  Read notes: {file_results['read_notes_time']:.4f}s")
        
        return result
    
    def should_terminate_early(self) -> bool:
        """Check if we should terminate based on performance degradation"""
        if len(self.results) < 2:
            return False
        
        # Compare last two iterations
        prev = self.results[-2]
        curr = self.results[-1]
        
        if prev.total_time == 0:
            return False
        
        increase = (curr.total_time - prev.total_time) / prev.total_time
        
        if increase > self.config.termination_threshold:
            print(f"\n⚠ Performance degraded by {increase*100:.1f}% - terminating early")
            return True
        
        return False
    
    def run_benchmark(self):
        """Run the complete benchmark"""
        print(f"{'='*70}")
        print("AVER PERFORMANCE BENCHMARK (JSON IO Mode)")
        print(f"{'='*70}")
        print(f"\nConfiguration:")
        print(f"  Starting records: {self.config.starting_records}")
        print(f"  Upper limit: {self.config.upper_limit}")
        print(f"  Records per iteration: {self.config.records_per_iteration}")
        print(f"  Notes per record: {self.config.notes_per_record}")
        print(f"  Termination threshold: {self.config.termination_threshold*100:.0f}%")
        print(f"  Test directory: {self.config.test_dir}")
        
        # Initialize database
        self.initialize_database()
        
        # Start JSON IO process for fast data injection
        print("\nStarting JSON IO interface...")
        self.start_json_io()
        
        try:
            iteration = 1
            while self.current_total_records < self.config.upper_limit:
                result = self.run_iteration(iteration)
                self.results.append(result)
                
                # Check for early termination
                if self.should_terminate_early():
                    break
                
                iteration += 1
            
        finally:
            # Always stop the JSON IO process
            print("\nStopping JSON IO interface...")
            self.stop_json_io()
        
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
        description="Benchmark aver.py performance limits (using JSON IO)",
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
1. Start a persistent JSON IO interface for fast data injection
2. Create records incrementally (default: 100 per iteration)
3. Add notes to each record (default: 5 per record)
4. Measure search and file access performance
5. Terminate early if performance degrades >30% between iterations
6. Provide recommendations based on results

This version uses JSON IO which is much faster than spawning separate processes!
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
