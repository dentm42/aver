#!/bin/bash
#
# Example benchmark scenarios for aver.py
#
# This script demonstrates different ways to use the benchmark tool
# and provides ready-to-run commands for common scenarios.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_scenario() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_command() {
    echo -e "${GREEN}Command:${NC} $1"
    echo ""
}

# Check if aver.py exists
if [ ! -f "aver.py" ]; then
    echo "Error: aver.py not found in current directory"
    echo "Please run this script from the directory containing aver.py"
    exit 1
fi

# Check if benchmark exists
if [ ! -f "benchmark_aver.py" ]; then
    echo "Error: benchmark_aver.py not found in current directory"
    echo "Please ensure benchmark_aver.py is in the same directory"
    exit 1
fi

echo -e "${YELLOW}Aver Performance Benchmark - Example Scenarios${NC}"
echo ""
echo "This script demonstrates different benchmark scenarios."
echo "Uncomment the scenario you want to run, or run commands manually."
echo ""
echo "Note: Each scenario creates temporary test data that is cleaned up automatically."
echo ""

# ============================================================================
# SCENARIO 1: Quick Performance Check
# ============================================================================
print_scenario "Scenario 1: Quick Performance Check (5-10 minutes)"
echo "Purpose: Get a quick sense of system performance limits"
echo "Use case: Initial testing, quick validation"
echo ""
print_command "./benchmark_aver.py --upper-limit 2000 --threshold 0.25"
echo "What it does:"
echo "  - Tests up to 2,000 records"
echo "  - Stops if performance degrades by 25%"
echo "  - Each record gets 5 notes (default)"
echo "  - Uses temporary directory (auto-cleanup)"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --upper-limit 2000 --threshold 0.25

# ============================================================================
# SCENARIO 2: Comprehensive Baseline
# ============================================================================
print_scenario "Scenario 2: Comprehensive Baseline (15-30 minutes)"
echo "Purpose: Establish performance baseline for your system"
echo "Use case: Initial deployment, performance documentation"
echo ""
print_command "./benchmark_aver.py --upper-limit 10000 --output baseline.json"
echo "What it does:"
echo "  - Tests up to 10,000 records"
echo "  - Default 30% termination threshold"
echo "  - Saves results to baseline.json for comparison"
echo "  - Provides statistical analysis"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --upper-limit 10000 --output baseline.json

# ============================================================================
# SCENARIO 3: Update-Heavy Workload
# ============================================================================
print_scenario "Scenario 3: Update-Heavy Workload (20-40 minutes)"
echo "Purpose: Test performance with many notes per record"
echo "Use case: Systems with frequent updates/comments"
echo ""
print_command "./benchmark_aver.py --upper-limit 5000 --notes-per-record 20 --output note_heavy.json"
echo "What it does:"
echo "  - Tests up to 5,000 records"
echo "  - Each record gets 20 notes (vs. 5 default)"
echo "  - Tests 100,000 total notes"
echo "  - Identifies if note reading is bottleneck"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --upper-limit 5000 --notes-per-record 20 --output note_heavy.json

# ============================================================================
# SCENARIO 4: Large Scale Test
# ============================================================================
print_scenario "Scenario 4: Large Scale Test (30-60 minutes)"
echo "Purpose: Find absolute limits on your hardware"
echo "Use case: Planning for growth, capacity testing"
echo ""
print_command "./benchmark_aver.py --starting-records 1000 --upper-limit 50000 --records-per-iteration 500 --output large_scale.json"
echo "What it does:"
echo "  - Starts with 1,000 records"
echo "  - Tests up to 50,000 records"
echo "  - Adds 500 records per iteration (faster)"
echo "  - Shows scaling characteristics"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --starting-records 1000 --upper-limit 50000 --records-per-iteration 500 --output large_scale.json

# ============================================================================
# SCENARIO 5: Incremental Growth Testing
# ============================================================================
print_scenario "Scenario 5: Incremental Growth Testing"
echo "Purpose: Test how system performs as it grows over time"
echo "Use case: Understanding long-term performance trajectory"
echo ""
echo "Step 1: Initial baseline (0-1k records)"
print_command "./benchmark_aver.py --upper-limit 1000 --test-dir ./growth_test --output growth_1k.json"
echo ""
echo "Step 2: Medium scale (1k-5k records)"
print_command "./benchmark_aver.py --starting-records 1000 --upper-limit 5000 --test-dir ./growth_test --output growth_5k.json"
echo ""
echo "Step 3: Large scale (5k-20k records)"
print_command "./benchmark_aver.py --starting-records 5000 --upper-limit 20000 --test-dir ./growth_test --output growth_20k.json"
echo ""
echo "What it does:"
echo "  - Uses same test directory across runs"
echo "  - Builds on previous data"
echo "  - Shows cumulative performance impact"
echo "  - Three separate result files for comparison"
echo ""
# Uncomment to run:
# mkdir -p growth_test
# ./benchmark_aver.py --upper-limit 1000 --test-dir ./growth_test --output growth_1k.json
# ./benchmark_aver.py --starting-records 1000 --upper-limit 5000 --test-dir ./growth_test --output growth_5k.json
# ./benchmark_aver.py --starting-records 5000 --upper-limit 20000 --test-dir ./growth_test --output growth_20k.json

# ============================================================================
# SCENARIO 6: Aggressive Performance Monitoring
# ============================================================================
print_scenario "Scenario 6: Aggressive Performance Monitoring"
echo "Purpose: Find exact point where performance drops"
echo "Use case: Fine-tuning capacity limits"
echo ""
print_command "./benchmark_aver.py --upper-limit 10000 --threshold 0.15 --records-per-iteration 50 --output aggressive.json"
echo "What it does:"
echo "  - Low 15% threshold (vs. 30% default)"
echo "  - Smaller iteration size (50 vs. 100)"
echo "  - More data points"
echo "  - Catches performance degradation earlier"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --upper-limit 10000 --threshold 0.15 --records-per-iteration 50 --output aggressive.json

# ============================================================================
# SCENARIO 7: Custom Hardware Testing
# ============================================================================
print_scenario "Scenario 7: Custom Hardware Testing"
echo "Purpose: Test on specific hardware (SSD vs HDD, etc.)"
echo "Use case: Hardware selection, optimization validation"
echo ""
echo "SSD Test:"
print_command "./benchmark_aver.py --upper-limit 10000 --test-dir /ssd/mount/benchmark --output ssd_results.json"
echo ""
echo "HDD Test:"
print_command "./benchmark_aver.py --upper-limit 10000 --test-dir /hdd/mount/benchmark --output hdd_results.json"
echo ""
echo "What it does:"
echo "  - Same test on different storage"
echo "  - Compare results to see hardware impact"
echo "  - Helps justify hardware decisions"
echo ""
# Uncomment to run (adjust paths):
# ./benchmark_aver.py --upper-limit 10000 --test-dir /path/to/ssd --output ssd_results.json
# ./benchmark_aver.py --upper-limit 10000 --test-dir /path/to/hdd --output hdd_results.json

# ============================================================================
# SCENARIO 8: Minimum Viable Performance
# ============================================================================
print_scenario "Scenario 8: Minimum Viable Performance"
echo "Purpose: Find smallest scale where performance is acceptable"
echo "Use case: Setting minimum requirements"
echo ""
print_command "./benchmark_aver.py --starting-records 100 --upper-limit 10000 --threshold 0.50 --output mvp.json"
echo "What it does:"
echo "  - Starts small (100 records)"
echo "  - Tolerant threshold (50%)"
echo "  - Runs longer to find real limits"
echo "  - Identifies minimum acceptable scale"
echo ""
# Uncomment to run:
# ./benchmark_aver.py --starting-records 100 --upper-limit 10000 --threshold 0.50 --output mvp.json

# ============================================================================
# Post-Run Analysis Commands
# ============================================================================
print_scenario "Post-Run Analysis"
echo "After running benchmarks, you can analyze results:"
echo ""
echo "1. View JSON results:"
echo -e "   ${GREEN}cat baseline.json | jq '.results[] | {records: .total_records, time: .total_time}'${NC}"
echo ""
echo "2. Compare first and last iteration:"
echo -e "   ${GREEN}cat baseline.json | jq '{first: .results[0], last: .results[-1]}'${NC}"
echo ""
echo "3. Extract just search times:"
echo -e "   ${GREEN}cat baseline.json | jq '.results[] | {records: .total_records, search_time: (.search_list_time + .search_query_time + .search_view_time)}'${NC}"
echo ""
echo "4. Find iteration with worst performance:"
echo -e "   ${GREEN}cat baseline.json | jq '.results | max_by(.total_time)'${NC}"
echo ""

# ============================================================================
# Recommendations
# ============================================================================
print_scenario "Recommendations"
echo "For first-time users:"
echo "  1. Start with Scenario 1 (Quick Check)"
echo "  2. Review the output and recommendations"
echo "  3. If performance is good, run Scenario 2 (Comprehensive)"
echo ""
echo "For production planning:"
echo "  1. Run Scenario 2 to establish baseline"
echo "  2. Run Scenario 3 if you expect many updates"
echo "  3. Run Scenario 4 to understand absolute limits"
echo ""
echo "For troubleshooting:"
echo "  1. Run Scenario 6 (Aggressive Monitoring)"
echo "  2. Compare with earlier results"
echo "  3. Identify which operations degraded"
echo ""

echo ""
echo -e "${YELLOW}To run any scenario, uncomment the relevant line in this script${NC}"
echo -e "${YELLOW}or copy the command and run it directly.${NC}"
echo ""
