# Aver Performance Benchmark

A comprehensive benchmarking tool for testing the performance limits of the aver knowledge tracking system.

## Overview

The aver system uses Markdown files with YAML frontmatter as the source of truth, with SQLite providing a fast search index layer. This benchmark helps determine the practical performance limits based on:

- **Number of records**: How many knowledge records the system can handle
- **Number of notes**: How many updates/notes per record
- **Search performance**: Speed of list, query, and view operations
- **File access performance**: Speed of direct file reading operations

## Key Features

- **Incremental testing**: Adds records progressively rather than starting from scratch each iteration
- **Automatic termination**: Stops early if performance degrades by more than 30% (configurable)
- **Comprehensive metrics**: Measures both search operations and direct file access
- **Statistical analysis**: Provides min/max/avg/median across all iterations
- **JSON export**: Save results for further analysis
- **Recommendations**: Suggests practical limits based on your configuration

## Installation

No additional dependencies required beyond what aver.py needs:

```bash
# Ensure you have aver.py and its dependencies installed
pip install pyyaml  # If not already installed

# Make the benchmark executable
chmod +x benchmark_aver.py
```

## Usage

### Basic Usage

Test up to 10,000 records with default settings:

```bash
./benchmark_aver.py --upper-limit 10000
```

### Common Scenarios

**Quick test** (find limits quickly):
```bash
./benchmark_aver.py --upper-limit 5000 --threshold 0.20
```

**Comprehensive test** (start with existing data):
```bash
./benchmark_aver.py --starting-records 1000 --upper-limit 50000
```

**Heavy note usage** (test systems with many updates):
```bash
./benchmark_aver.py --upper-limit 20000 --notes-per-record 10
```

**Custom test directory** (reuse between runs):
```bash
./benchmark_aver.py --upper-limit 10000 --test-dir ./benchmark_data
```

**Save results for analysis**:
```bash
./benchmark_aver.py --upper-limit 20000 --output results.json
```

### Advanced Usage

**Test incremental growth** (add to existing benchmark):
```bash
# First run
./benchmark_aver.py --upper-limit 10000 --test-dir ./my_test

# Later: continue from 10k to 20k
./benchmark_aver.py --starting-records 10000 --upper-limit 20000 --test-dir ./my_test
```

**Aggressive performance monitoring**:
```bash
./benchmark_aver.py --upper-limit 50000 --threshold 0.15 --records-per-iteration 50
```

## Command-Line Options

### Required

- `--upper-limit N`: Maximum number of records to test (required)

### Optional

- `--aver-path PATH`: Path to aver.py script (default: ./aver.py)
- `--starting-records N`: Number of records to start with (default: 100)
- `--records-per-iteration N`: Records to add each iteration (default: 100)
- `--notes-per-record N`: Notes to add to each record (default: 5)
- `--threshold FLOAT`: Early termination threshold (default: 0.30 = 30%)
- `--test-dir PATH`: Directory for test data (default: temporary directory)
- `--output PATH`: JSON file for results
- `--verbose`: Show detailed output

## How It Works

### Benchmark Process

1. **Initialization**: Creates a fresh aver database in test directory
2. **Initial batch**: Creates starting number of records with notes
3. **Iterations**:
   - Add more records with notes
   - Measure search operations:
     - List all records
     - Search by keyword
     - View specific record
   - Measure file operations:
     - Direct read of record markdown file
     - Direct read of all note files
4. **Termination check**: Compare current iteration time with previous
   - If increase > threshold (default 30%), stop early
5. **Summary**: Statistical analysis and recommendations

### What Gets Measured

**Search Operations:**
- `search_list_time`: Time to list all records (tests database query)
- `search_query_time`: Time to search for keyword (tests index performance)
- `search_view_time`: Time to view a specific record (tests lookup + parse)

**File Operations:**
- `file_read_record_time`: Time to read a record markdown file directly
- `file_read_notes_time`: Time to read all notes for a record

**Derived Metrics:**
- `total_time`: Sum of all operations
- `records_per_second`: Throughput measure
- `notes_per_second`: Throughput measure

### Early Termination Logic

The benchmark automatically stops if performance degrades significantly between iterations. This prevents wasting time on configurations that clearly won't scale.

**Example**: If iteration 5 takes 2.0s and iteration 6 takes 2.7s (35% increase), the benchmark stops since it exceeds the 30% default threshold.

## Output Format

### Console Output

```
=====================================================================
Iteration 3
=====================================================================
Creating 100 records...
  Adding 5 notes to REC-00251...
  [...]

Current state:
  Total records: 300
  Notes per record: 5
  Total notes: 1500

Benchmarking search operations...
Benchmarking file operations...

Results:
  Search list: 0.1234s
  Search query: 0.0856s
  Search view: 0.0234s
  File read record: 0.0012s
  File read notes: 0.0067s
  Total time: 0.2403s
  Records/sec: 1248.44
  Notes/sec: 6242.19
```

### JSON Output

```json
{
  "config": {
    "starting_records": 100,
    "upper_limit": 10000,
    "records_per_iteration": 100,
    "notes_per_record": 5,
    "termination_threshold": 0.3
  },
  "results": [
    {
      "iteration": 1,
      "total_records": 100,
      "total_notes": 500,
      "search_list_time": 0.0234,
      "search_query_time": 0.0156,
      "total_time": 0.1234,
      "records_per_second": 810.37
    }
  ],
  "summary": {
    "iterations": 5,
    "final_records": 500,
    "final_notes": 2500
  }
}
```

## Interpreting Results

### Performance Indicators

**Good Performance** (Total time < 1 second):
- System is fast and responsive
- Can likely handle 2-3x more records
- Suitable for real-time interactive use

**Acceptable Performance** (Total time 1-5 seconds):
- System is slowing but usable
- Current scale is a reasonable soft limit
- Consider optimization if growth expected

**Degraded Performance** (Total time > 5 seconds):
- System is struggling at this scale
- Recommend using 50% of current records as limit
- May need architectural changes for larger scale

### Scaling Characteristics

The benchmark helps identify which operations scale poorly:

- **Linear scaling**: Time increases proportionally with records (good)
- **Quadratic scaling**: Time increases exponentially (bad)
- **Constant time**: Time stays same regardless of scale (excellent)

Example analysis:
```
If search_list_time grows from 0.1s → 0.2s → 0.4s → 0.8s
→ This is quadratic scaling, list operation is the bottleneck

If search_view_time stays at ~0.01s regardless of total records
→ This is constant time, view operation scales well
```

## Real-World Recommendations

Based on typical usage patterns:

### Small Projects (1-1,000 records)
- **Recommendation**: Unlimited, system will be very fast
- **Benchmark**: `--upper-limit 1000` (quick validation)

### Medium Projects (1,000-10,000 records)
- **Recommendation**: Run benchmark to find exact limits
- **Benchmark**: `--upper-limit 10000 --notes-per-record 10`

### Large Projects (10,000-100,000 records)
- **Recommendation**: Expect some slowdown, test thoroughly
- **Benchmark**: `--upper-limit 100000 --threshold 0.20`
- **Consider**: Splitting into multiple aver instances

### Enterprise Scale (100,000+ records)
- **Recommendation**: Architectural review needed
- **Benchmark**: `--upper-limit 100000 --starting-records 10000`
- **Consider**: Database-backed source of truth instead of files

## Performance Optimization Tips

Based on benchmark results, consider:

1. **If search is slow**: SQLite index may need optimization
2. **If file reading is slow**: Consider SSD storage, check filesystem
3. **If both are slow**: Too many records for file-based system
4. **If early termination happens**: You've found practical limit

## Limitations

### What This Benchmark Does NOT Test

- **Full-text search**: Not yet implemented in aver
- **Concurrent access**: Only tests single-user performance
- **Network latency**: Assumes local filesystem
- **Large record content**: Uses minimal content (tests count, not size)
- **Complex queries**: Only basic search patterns

### Known Considerations

- **File size impact**: Very large individual records/notes not tested
- **Filesystem limits**: Some filesystems have directory entry limits
- **Memory usage**: Not directly measured, but affects performance
- **Disk space**: Benchmark doesn't track storage requirements

## Troubleshooting

### "Cannot find aver.py"
```bash
# Specify path explicitly
./benchmark_aver.py --aver-path /path/to/aver.py --upper-limit 1000
```

### "Benchmark too slow"
```bash
# Reduce starting records and increase iteration size
./benchmark_aver.py --starting-records 50 --records-per-iteration 200 --upper-limit 5000
```

### "Early termination too aggressive"
```bash
# Increase threshold to 50%
./benchmark_aver.py --threshold 0.50 --upper-limit 10000
```

### "Want to continue from previous run"
```bash
# Use same test directory and higher starting point
./benchmark_aver.py --test-dir ./my_test --starting-records 5000 --upper-limit 10000
```

## Examples

### Example 1: Quick Validation
```bash
# Find where performance starts degrading
./benchmark_aver.py --upper-limit 5000 --threshold 0.25 --output quick_test.json

# Expected output:
# - Runs until 30% slowdown detected
# - Shows which operation is bottleneck
# - Recommends practical limit
```

### Example 2: Note-Heavy System
```bash
# Test system with lots of updates per record
./benchmark_aver.py --upper-limit 10000 --notes-per-record 20 --output note_heavy.json

# Expected output:
# - Shows if note reading is bottleneck
# - Helps optimize update-heavy workflows
```

### Example 3: Incremental Growth
```bash
# Test: Start small, grow to large
./benchmark_aver.py --starting-records 100 --upper-limit 50000 \
  --records-per-iteration 500 --output growth_test.json

# Expected output:
# - Shows scaling curve over wide range
# - Identifies inflection points
# - Clear performance trend analysis
```

## Contributing

To extend this benchmark:

1. Add new operations to measure in `benchmark_*_operations()` methods
2. Add new metrics to `BenchmarkResult` dataclass
3. Update summary statistics in `print_summary()`
4. Document new metrics in this README

## License

Same as aver.py - see main project license.
