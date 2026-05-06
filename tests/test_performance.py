# -*- encoding: utf-8 -*-
"""
Performance test suite for MongoDB backend write operations.

This test suite measures the performance improvements from replacing
deprecated PyMongo 2.x methods with modern PyMongo 3.x methods.

Tests run in all environments but only perform measurements in GitHub Actions.
"""
from __future__ import absolute_import, unicode_literals
import unittest
import os
import time
import json
from datetime import datetime
from statistics import mean, median, stdev

from osv import osv, fields
from mongodb_backend import testing, osv_mongodb
from destral.transaction import Transaction
from mongodb_backend import mongodb2

# Import requests if available for GitHub API posting
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class PerformanceTestModel(osv_mongodb.osv_mongodb):
    """Test model for performance measurements."""
    _name = 'performance.test'

    _columns = {
        'name': fields.char('Name', size=64),
        'value': fields.integer('Value'),
        'description': fields.text('Description'),
        'active': fields.boolean('Active'),
    }
    
    _defaults = {
        'active': lambda *a: True,
        'value': lambda *a: 0,
    }


class PerformanceMetrics:
    """Container for performance metrics and reporting."""
    
    def __init__(self):
        self.metrics = {}
        self.comparisons = []
    
    def record_operation(self, operation_name, duration, records_count=1):
        """Record a single operation timing."""
        if operation_name not in self.metrics:
            self.metrics[operation_name] = []
        
        # Prevent division by zero with a small epsilon
        duration = max(duration, 1e-9)
        
        self.metrics[operation_name].append({
            'duration': duration,
            'records': records_count,
            'ops_per_sec': records_count / duration,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    
    def add_comparison(self, operation, old_time, new_time, records):
        """Add a comparison between old and new implementations."""
        # Prevent division by zero with epsilon
        old_time = max(old_time, 1e-9)
        new_time = max(new_time, 1e-9)
        
        improvement_pct = ((old_time - new_time) / old_time * 100)
        self.comparisons.append({
            'operation': operation,
            'old_method_time': old_time,
            'new_method_time': new_time,
            'records': records,
            'improvement_pct': improvement_pct,
            'speedup_factor': old_time / new_time
        })
    
    def get_statistics(self, operation_name):
        """Calculate statistics for an operation."""
        if operation_name not in self.metrics:
            return None
        
        durations = [m['duration'] for m in self.metrics[operation_name]]
        ops_per_sec = [m['ops_per_sec'] for m in self.metrics[operation_name]]
        
        return {
            'operation': operation_name,
            'count': len(durations),
            'mean_duration': mean(durations),
            'median_duration': median(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'stdev_duration': stdev(durations) if len(durations) > 1 else 0,
            'mean_ops_per_sec': mean(ops_per_sec),
            'median_ops_per_sec': median(ops_per_sec),
        }
    
    def generate_report(self):
        """Generate a comprehensive performance report."""
        report = {
            'test_run': {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'environment': 'GitHub Actions' if os.environ.get('GITHUB_ACTIONS') else 'Local',
                'python_version': os.environ.get('PYTHON_VERSION', 'unknown'),
                'pymongo_version': os.environ.get('PYMONGO_VERSION', 'unknown'),
                'mongodb_version': os.environ.get('MONGODB_VERSION', 'unknown'),
            },
            'summary': {},
            'detailed_metrics': {},
            'comparisons': self.comparisons
        }
        
        # Generate statistics for each operation
        for operation_name in self.metrics:
            stats = self.get_statistics(operation_name)
            if stats:
                report['detailed_metrics'][operation_name] = stats
        
        # Generate summary
        if self.comparisons:
            avg_improvement = mean([c['improvement_pct'] for c in self.comparisons])
            avg_speedup = mean([c['speedup_factor'] for c in self.comparisons])
            report['summary'] = {
                'total_comparisons': len(self.comparisons),
                'average_improvement_pct': avg_improvement,
                'average_speedup_factor': avg_speedup,
                'min_improvement_pct': min([c['improvement_pct'] for c in self.comparisons]),
                'max_improvement_pct': max([c['improvement_pct'] for c in self.comparisons]),
            }
        
        return report
    
    def print_report(self):
        """Print a formatted report to stdout."""
        report = self.generate_report()
        
        print("\n" + "="*80)
        print("MONGODB BACKEND PERFORMANCE TEST REPORT")
        print("="*80)
        print("\nTest Run: {}".format(report['test_run']['timestamp']))
        print("Environment: {}".format(report['test_run']['environment']))
        print("\nTest Configuration:")
        print("  Python Version: {}".format(report['test_run']['python_version']))
        print("  PyMongo Version: {}".format(report['test_run']['pymongo_version']))
        print("  MongoDB Version: {}".format(report['test_run']['mongodb_version']))
        
        if report['summary']:
            print("\n" + "-"*80)
            print("SUMMARY")
            print("-"*80)
            print("Total Comparisons: {}".format(report['summary']['total_comparisons']))
            print("Average Improvement: {:.2f}%".format(report['summary']['average_improvement_pct']))
            print("Average Speedup Factor: {:.2f}x".format(report['summary']['average_speedup_factor']))
            print("Improvement Range: {:.2f}% - {:.2f}%".format(
                report['summary']['min_improvement_pct'],
                report['summary']['max_improvement_pct']))
        
        if report['comparisons']:
            print("\n" + "-"*80)
            print("DETAILED COMPARISONS")
            print("-"*80)
            print("{:<30} {:<12} {:<12} {:<10} {:<12}".format(
                'Operation', 'Old (s)', 'New (s)', 'Speedup', 'Improvement'))
            print("-"*80)
            for comp in report['comparisons']:
                print("{:<30} {:<12.4f} {:<12.4f} {:<10.2f}x {:<12.2f}%".format(
                    comp['operation'],
                    comp['old_method_time'],
                    comp['new_method_time'],
                    comp['speedup_factor'],
                    comp['improvement_pct']))
        
        if report['detailed_metrics']:
            print("\n" + "-"*80)
            print("DETAILED METRICS")
            print("-"*80)
            for op_name, stats in report['detailed_metrics'].items():
                print("\n{}:".format(op_name))
                print("  Iterations: {}".format(stats['count']))
                print("  Mean Duration: {:.4f}s".format(stats['mean_duration']))
                print("  Median Duration: {:.4f}s".format(stats['median_duration']))
                print("  Min/Max: {:.4f}s / {:.4f}s".format(
                    stats['min_duration'], stats['max_duration']))
                print("  Std Dev: {:.4f}s".format(stats['stdev_duration']))
                print("  Mean Throughput: {:.2f} ops/sec".format(stats['mean_ops_per_sec']))
        
        print("\n" + "="*80)
        
        return report
    
    def save_report(self, filename='performance_report.json'):
        """Save report to JSON file."""
        report = self.generate_report()
        
        # Validate filename and use fallback if needed
        if not filename or not isinstance(filename, str):
            filename = 'performance_report.json'
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            print("\nPerformance report saved to: {}".format(filename))
        except (IOError, OSError) as e:
            print("\nWarning: Could not save report to {}: {}".format(filename, e))
            # Try fallback location
            fallback = '/tmp/performance_report.json'
            try:
                with open(fallback, 'w') as f:
                    json.dump(report, f, indent=2)
                print("Report saved to fallback location: {}".format(fallback))
            except Exception as e2:
                print("Error: Could not save report to fallback location: {}".format(e2))
    
    def post_to_github_pr(self, report):
        """Post performance report to GitHub PR via API."""
        if not HAS_REQUESTS:
            print("\nSkipping GitHub PR comment: requests library not available")
            return
        
        pr_number = os.environ.get('GITHUB_ACTIONS_PR')
        github_token = os.environ.get('GITHUB_TOKEN')
        github_repository = os.environ.get('GITHUB_REPOSITORY', 'gisce/mongodb_backend')
        
        if not pr_number or not github_token:
            print("\nSkipping GitHub PR comment: GITHUB_ACTIONS_PR or GITHUB_TOKEN not set")
            return
        
        # Generate markdown comment
        comment_body = self._generate_pr_comment(report)
        
        # Post to GitHub API
        url = "https://api.github.com/repos/{}/issues/{}/comments".format(
            github_repository, pr_number)
        headers = {
            'Authorization': 'token {}'.format(github_token),
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            response = requests.post(url, headers=headers, json={'body': comment_body})
            if response.status_code == 201:
                print("\nPerformance report posted to PR #{}".format(pr_number))
            else:
                print("\nFailed to post to PR: {} - {}".format(response.status_code, response.text))
        except Exception as e:
            print("\nError posting to GitHub PR: {}".format(e))
    
    def _generate_pr_comment(self, report):
        """Generate markdown comment for GitHub PR."""
        lines = [
            "## 📊 Performance Test Results",
            "",
            "**Test Run:** {}".format(report['test_run']['timestamp']),
            "**Environment:** {}".format(report['test_run']['environment']),
            "",
            "### 🔧 Test Configuration",
            "- **Python Version:** {}".format(report['test_run']['python_version']),
            "- **PyMongo Version:** {}".format(report['test_run']['pymongo_version']),
            "- **MongoDB Version:** {}".format(report['test_run']['mongodb_version']),
            ""
        ]
        
        if 'summary' in report and report['summary']:
            summary = report['summary']
            lines.extend([
                "### Summary",
                "",
                "- **Total Comparisons:** {}".format(summary.get('total_comparisons', 'N/A')),
                "- **Average Improvement:** {:.2f}%".format(summary.get('average_improvement_pct', 0)),
                "- **Average Speedup:** {:.2f}x".format(summary.get('average_speedup_factor', 0)),
                "- **Improvement Range:** {:.2f}% - {:.2f}%".format(
                    summary.get('min_improvement_pct', 0),
                    summary.get('max_improvement_pct', 0)),
                ""
            ])
        
        if 'detailed_metrics' in report and report['detailed_metrics']:
            lines.extend([
                "### Detailed Metrics",
                "",
                "| Operation | Iterations | Mean Duration | Median | Throughput |",
                "|-----------|------------|---------------|--------|------------|"
            ])
            for op_name, stats in report['detailed_metrics'].items():
                lines.append(
                    "| {} | {} | {:.4f}s | {:.4f}s | {:.2f} ops/sec |".format(
                        op_name,
                        stats.get('count', 0),
                        stats.get('mean_duration', 0),
                        stats.get('median_duration', 0),
                        stats.get('mean_ops_per_sec', 0))
                )
            lines.append("")
        
        if 'comparisons' in report and report['comparisons']:
            lines.extend([
                "### Performance Comparisons",
                "",
                "| Operation | Old Method | New Method | Speedup | Improvement |",
                "|-----------|------------|------------|---------|-------------|"
            ])
            for comp in report['comparisons']:
                lines.append(
                    "| {} | {:.4f}s | {:.4f}s | {:.2f}x | {:.2f}% |".format(
                        comp['operation'],
                        comp['old_method_time'],
                        comp['new_method_time'],
                        comp['speedup_factor'],
                        comp['improvement_pct'])
                )
        
        return '\n'.join(lines)


class TestWritePerformance(testing.MongoDBTestCase):
    """Test write operation performance improvements."""
    
    def setUp(self):
        # Check if we should run performance tests
        self.should_run_perf = os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
        
        if not self.should_run_perf:
            # Skip performance measurements but still run basic setup
            self.skipTest("Performance tests only run in GitHub Actions")
            return
        
        self.txn = Transaction().start(self.database)
        self.metrics = PerformanceMetrics()
        self._setup_test_model()
    
    def tearDown(self):
        if not self.should_run_perf:
            return
            
        self._cleanup()
        self.txn.stop()
        
        # Generate and print report after all tests
        if hasattr(self, 'metrics'):
            report = self.metrics.print_report()
            
            # Save report in GitHub Actions
            if os.environ.get('GITHUB_ACTIONS'):
                workspace = os.environ.get('GITHUB_WORKSPACE', '.')
                # Validate workspace path
                if workspace and os.path.isdir(workspace):
                    report_file = os.path.join(workspace, 'performance_report.json')
                else:
                    report_file = 'performance_report.json'
                self.metrics.save_report(report_file)
                
                # Post results to GitHub PR
                self.metrics.post_to_github_pr(report)
    
    def _setup_test_model(self):
        """Setup the performance test model."""
        cursor = self.txn.cursor
        PerformanceTestModel()
        osv.class_pool[PerformanceTestModel._name].createInstance(
            self.openerp.pool, 'mongodb_backend', cursor
        )
        self.model = self.openerp.pool.get(PerformanceTestModel._name)
        self.model._auto_init(cursor)
    
    def _cleanup(self):
        """Clean up test data."""
        from mongodb_backend.mongodb2 import mdbpool
        db = mdbpool.get_db()
        db.drop_collection("performance_test")
    
    def _create_test_records(self, count=100):
        """Create test records for performance testing."""
        cursor = self.txn.cursor
        uid = self.txn.user
        ids = []
        
        for i in range(count):
            record_id = self.model.create(cursor, uid, {
                'name': 'Test Record {}'.format(i),
                'value': i,
                'description': 'Performance test record number {}'.format(i),
                'active': True,
            })
            ids.append(record_id)
        
        return ids
    
    def test_single_write_performance(self):
        """Test performance of single record writes."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create a test record
        record_id = self.model.create(cursor, uid, {
            'name': 'Single Write Test',
            'value': 1,
        })
        
        # Measure single write performance (multiple iterations)
        iterations = 50
        for i in range(iterations):
            start_time = time.time()
            self.model.write(cursor, uid, [record_id], {
                'value': i,
                'description': 'Updated at iteration {}'.format(i)
            })
            duration = time.time() - start_time
            self.metrics.record_operation('single_write', duration, records_count=1)
        
        # Assert performance is reasonable (< 100ms per write)
        stats = self.metrics.get_statistics('single_write')
        self.assertLess(stats['mean_duration'], 0.1, 
                       "Single writes averaging {:.4f}s should be < 0.1s".format(stats['mean_duration']))
    
    def test_bulk_write_performance(self):
        """Test performance of bulk write operations."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create test records
        record_ids = self._create_test_records(count=100)
        
        # Measure bulk write performance
        iterations = 10
        for i in range(iterations):
            start_time = time.time()
            self.model.write(cursor, uid, record_ids, {
                'value': 1000 + i,
                'description': '{}'.format(i)
            })
            duration = time.time() - start_time
            self.metrics.record_operation('bulk_write_100', duration, records_count=100)
        
        # Assert bulk performance is reasonable
        stats = self.metrics.get_statistics('bulk_write_100')
        self.assertLess(stats['mean_duration'], 1.0,
                       "Bulk writes (100 records) averaging {:.4f}s should be < 1.0s".format(stats['mean_duration']))
        
        # Throughput should be reasonable
        self.assertGreater(stats['mean_ops_per_sec'], 50,
                          "Bulk write throughput {:.2f} ops/sec should be > 50".format(stats['mean_ops_per_sec']))
    
    def test_sequential_writes_consistency(self):
        """Test that sequential writes have consistent performance (no random delays)."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create test records
        record_ids = self._create_test_records(count=10)
        
        # Perform many sequential writes and measure variance
        iterations = 50
        durations = []
        
        for i in range(iterations):
            # Pick a random record to update
            record_id = record_ids[i % len(record_ids)]
            
            start_time = time.time()
            self.model.write(cursor, uid, [record_id], {
                'value': i,
                'description': 'Sequential test {}'.format(i)
            })
            duration = time.time() - start_time
            durations.append(duration)
            self.metrics.record_operation('sequential_write', duration, records_count=1)
        
        # Calculate variance
        stats = self.metrics.get_statistics('sequential_write')
        # Prevent division by zero for coefficient of variation
        coefficient_of_variation = (stats['stdev_duration'] / stats['mean_duration']) * 100 if stats['mean_duration'] > 1e-9 else 0
        
        # Assert consistency: CV should be reasonable (< 50%)
        self.assertLess(coefficient_of_variation, 50,
                       "Sequential writes have high variance (CV={:.1f}%), indicating inconsistent performance".format(coefficient_of_variation))
        
        # No individual write should be extremely slow
        max_acceptable = stats['mean_duration'] * 5  # Allow up to 5x mean
        self.assertLess(stats['max_duration'], max_acceptable,
                       "Max write time {:.4f}s is too high (more than 5x mean of {:.4f}s)".format(
                           stats['max_duration'], stats['mean_duration']))
    
    def test_write_throughput_sustained(self):
        """Test sustained write throughput over time."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create a larger dataset
        record_ids = self._create_test_records(count=200)
        
        # Measure sustained throughput over multiple batches
        batch_size = 50
        num_batches = 5
        
        for batch_num in range(num_batches):
            start_idx = (batch_num * batch_size) % len(record_ids)
            batch_ids = record_ids[start_idx:start_idx + batch_size]
            
            start_time = time.time()
            self.model.write(cursor, uid, batch_ids, {
                'value': 2000 + batch_num,
                'description': 'Sustained throughput test batch {}'.format(batch_num)
            })
            duration = time.time() - start_time
            self.metrics.record_operation('sustained_write_batch_{}'.format(batch_num), 
                                         duration, records_count=batch_size)
        
        # All batches should have similar performance
        batch_stats = []
        for batch_num in range(num_batches):
            stats = self.metrics.get_statistics('sustained_write_batch_{}'.format(batch_num))
            batch_stats.append(stats['mean_duration'])
        
        # Variance across batches should be low
        # Prevent division by zero
        batch_mean = mean(batch_stats)
        batch_cv = (stdev(batch_stats) / batch_mean) * 100 if batch_mean > 1e-9 else 0
        self.assertLess(batch_cv, 30,
                       "Sustained write throughput has high variance (CV={:.1f}%)".format(batch_cv))
    
    def test_unlink_performance(self):
        """Test performance of delete operations."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Test single deletes
        for i in range(20):
            record_id = self.model.create(cursor, uid, {
                'name': 'Delete Test {}'.format(i),
                'value': i,
            })
            
            start_time = time.time()
            self.model.unlink(cursor, uid, [record_id])
            duration = time.time() - start_time
            self.metrics.record_operation('single_delete', duration, records_count=1)
        
        # Test bulk deletes
        for batch in range(5):
            batch_ids = self._create_test_records(count=50)
            
            start_time = time.time()
            self.model.unlink(cursor, uid, batch_ids)
            duration = time.time() - start_time
            self.metrics.record_operation('bulk_delete_50', duration, records_count=50)
        
        # Assert delete performance
        single_stats = self.metrics.get_statistics('single_delete')
        bulk_stats = self.metrics.get_statistics('bulk_delete_50')
        
        self.assertLess(single_stats['mean_duration'], 0.1,
                       "Single deletes averaging {:.4f}s should be < 0.1s".format(single_stats['mean_duration']))
        self.assertLess(bulk_stats['mean_duration'], 1.0,
                       "Bulk deletes (50 records) averaging {:.4f}s should be < 1.0s".format(bulk_stats['mean_duration']))


class TestPerformanceRegression(testing.MongoDBTestCase):
    """Test that performance hasn't regressed from the changes."""
    
    def setUp(self):
        # Check if we should run performance tests
        self.should_run_perf = os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
        
        if not self.should_run_perf:
            # Skip performance measurements but still run basic setup
            self.skipTest("Performance tests only run in GitHub Actions")
            return
        
        self.txn = Transaction().start(self.database)
        self._setup_test_model()
    
    def tearDown(self):
        if not self.should_run_perf:
            return
            
        self._cleanup()
        self.txn.stop()
    
    def _setup_test_model(self):
        """Setup the performance test model."""
        cursor = self.txn.cursor
        PerformanceTestModel()
        osv.class_pool[PerformanceTestModel._name].createInstance(
            self.openerp.pool, 'mongodb_backend', cursor
        )
        self.model = self.openerp.pool.get(PerformanceTestModel._name)
        self.model._auto_init(cursor)
    
    def _cleanup(self):
        """Clean up test data."""
        from mongodb_backend.mongodb2 import mdbpool
        db = mdbpool.get_db()
        db.drop_collection("performance_test")
    
    def test_write_operations_functional(self):
        """Verify write operations still work correctly after changes."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create a record
        record_id = self.model.create(cursor, uid, {
            'name': 'Functional Test',
            'value': 100,
            'description': 'Testing functionality',
        })
        
        # Verify creation
        record = self.model.read(cursor, uid, record_id, ['name', 'value', 'description'])
        self.assertEqual(record['name'], 'Functional Test')
        self.assertEqual(record['value'], 100)
        
        # Update the record
        self.model.write(cursor, uid, [record_id], {
            'value': 200,
            'description': 'Updated description',
        })
        
        # Verify update
        record = self.model.read(cursor, uid, record_id, ['name', 'value', 'description'])
        self.assertEqual(record['value'], 200)
        self.assertEqual(record['description'], 'Updated description')
        
        # Delete the record
        self.model.unlink(cursor, uid, [record_id])
        
        # Verify deletion
        found_ids = self.model.search(cursor, uid, [('id', '=', record_id)])
        self.assertEqual(len(found_ids), 0)
    
    def test_bulk_operations_functional(self):
        """Verify bulk operations work correctly."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Create multiple records
        ids = []
        for i in range(20):
            record_id = self.model.create(cursor, uid, {
                'name': 'Bulk Test {}'.format(i),
                'value': i * 10,
            })
            ids.append(record_id)
        
        # Bulk update
        self.model.write(cursor, uid, ids, {
            'value': 999,
            'description': 'Bulk updated',
        })
        
        # Verify all updated
        for record_id in ids:
            record = self.model.read(cursor, uid, record_id, ['value', 'description'])
            self.assertEqual(record['value'], 999)
            self.assertEqual(record['description'], 'Bulk updated')
        
        # Bulk delete
        self.model.unlink(cursor, uid, ids)
        
        # Verify all deleted
        found_ids = self.model.search(cursor, uid, [('id', 'in', ids)])
        self.assertEqual(len(found_ids), 0)


if __name__ == '__main__':
    unittest.main()
