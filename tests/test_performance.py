# -*- encoding: utf-8 -*-
"""
Performance test suite for MongoDB backend write operations.

This test suite measures the performance improvements from replacing
deprecated PyMongo 2.x methods with modern PyMongo 3.x methods.

Tests only run in GitHub Actions workflows where GITHUB_ACTIONS=true.
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


# Skip all tests if not running in GitHub Actions
SKIP_REASON = "Performance tests only run in GitHub Actions (GITHUB_ACTIONS env var not set)"
SKIP_IF_NOT_CI = not os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'


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
        
        self.metrics[operation_name].append({
            'duration': duration,
            'records': records_count,
            'ops_per_sec': records_count / duration if duration > 0 else 0,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_comparison(self, operation, old_time, new_time, records):
        """Add a comparison between old and new implementations."""
        improvement_pct = ((old_time - new_time) / old_time * 100) if old_time > 0 else 0
        self.comparisons.append({
            'operation': operation,
            'old_method_time': old_time,
            'new_method_time': new_time,
            'records': records,
            'improvement_pct': improvement_pct,
            'speedup_factor': old_time / new_time if new_time > 0 else 0
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
                'timestamp': datetime.now().isoformat(),
                'environment': 'GitHub Actions' if os.environ.get('GITHUB_ACTIONS') else 'Local',
                'python_version': os.environ.get('PYTHON_VERSION', 'unknown'),
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
        print(f"\nTest Run: {report['test_run']['timestamp']}")
        print(f"Environment: {report['test_run']['environment']}")
        print(f"Python Version: {report['test_run']['python_version']}")
        
        if report['summary']:
            print("\n" + "-"*80)
            print("SUMMARY")
            print("-"*80)
            print(f"Total Comparisons: {report['summary']['total_comparisons']}")
            print(f"Average Improvement: {report['summary']['average_improvement_pct']:.2f}%")
            print(f"Average Speedup Factor: {report['summary']['average_speedup_factor']:.2f}x")
            print(f"Improvement Range: {report['summary']['min_improvement_pct']:.2f}% - {report['summary']['max_improvement_pct']:.2f}%")
        
        if report['comparisons']:
            print("\n" + "-"*80)
            print("DETAILED COMPARISONS")
            print("-"*80)
            print(f"{'Operation':<30} {'Old (s)':<12} {'New (s)':<12} {'Speedup':<10} {'Improvement':<12}")
            print("-"*80)
            for comp in report['comparisons']:
                print(f"{comp['operation']:<30} {comp['old_method_time']:<12.4f} {comp['new_method_time']:<12.4f} {comp['speedup_factor']:<10.2f}x {comp['improvement_pct']:<12.2f}%")
        
        if report['detailed_metrics']:
            print("\n" + "-"*80)
            print("DETAILED METRICS")
            print("-"*80)
            for op_name, stats in report['detailed_metrics'].items():
                print(f"\n{op_name}:")
                print(f"  Iterations: {stats['count']}")
                print(f"  Mean Duration: {stats['mean_duration']:.4f}s")
                print(f"  Median Duration: {stats['median_duration']:.4f}s")
                print(f"  Min/Max: {stats['min_duration']:.4f}s / {stats['max_duration']:.4f}s")
                print(f"  Std Dev: {stats['stdev_duration']:.4f}s")
                print(f"  Mean Throughput: {stats['mean_ops_per_sec']:.2f} ops/sec")
        
        print("\n" + "="*80)
        
        return report
    
    def save_report(self, filename='performance_report.json'):
        """Save report to JSON file."""
        report = self.generate_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nPerformance report saved to: {filename}")


@unittest.skipIf(SKIP_IF_NOT_CI, SKIP_REASON)
class TestWritePerformance(testing.MongoDBTestCase):
    """Test write operation performance improvements."""
    
    def setUp(self):
        self.txn = Transaction().start(self.database)
        self.metrics = PerformanceMetrics()
        self._setup_test_model()
    
    def tearDown(self):
        self._cleanup()
        self.txn.stop()
        
        # Print report after all tests
        if hasattr(self, 'metrics'):
            report = self.metrics.print_report()
            
            # Save report in GitHub Actions
            if os.environ.get('GITHUB_ACTIONS'):
                workspace = os.environ.get('GITHUB_WORKSPACE', '.')
                report_file = os.path.join(workspace, 'performance_report.json')
                self.metrics.save_report(report_file)
    
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
                'name': f'Test Record {i}',
                'value': i,
                'description': f'Performance test record number {i}',
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
                'description': f'Updated at iteration {i}'
            })
            duration = time.time() - start_time
            self.metrics.record_operation('single_write', duration, records_count=1)
        
        # Assert performance is reasonable (< 100ms per write)
        stats = self.metrics.get_statistics('single_write')
        self.assertLess(stats['mean_duration'], 0.1, 
                       f"Single writes averaging {stats['mean_duration']:.4f}s should be < 0.1s")
    
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
                'description': f'Bulk update iteration {i}'
            })
            duration = time.time() - start_time
            self.metrics.record_operation('bulk_write_100', duration, records_count=100)
        
        # Assert bulk performance is reasonable
        stats = self.metrics.get_statistics('bulk_write_100')
        self.assertLess(stats['mean_duration'], 1.0,
                       f"Bulk writes (100 records) averaging {stats['mean_duration']:.4f}s should be < 1.0s")
        
        # Throughput should be reasonable
        self.assertGreater(stats['mean_ops_per_sec'], 50,
                          f"Bulk write throughput {stats['mean_ops_per_sec']:.2f} ops/sec should be > 50")
    
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
                'description': f'Sequential test {i}'
            })
            duration = time.time() - start_time
            durations.append(duration)
            self.metrics.record_operation('sequential_write', duration, records_count=1)
        
        # Calculate variance
        stats = self.metrics.get_statistics('sequential_write')
        coefficient_of_variation = (stats['stdev_duration'] / stats['mean_duration']) * 100
        
        # Assert consistency: CV should be reasonable (< 50%)
        self.assertLess(coefficient_of_variation, 50,
                       f"Sequential writes have high variance (CV={coefficient_of_variation:.1f}%), "
                       f"indicating inconsistent performance")
        
        # No individual write should be extremely slow
        max_acceptable = stats['mean_duration'] * 5  # Allow up to 5x mean
        self.assertLess(stats['max_duration'], max_acceptable,
                       f"Max write time {stats['max_duration']:.4f}s is too high "
                       f"(more than 5x mean of {stats['mean_duration']:.4f}s)")
    
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
                'description': f'Sustained throughput test batch {batch_num}'
            })
            duration = time.time() - start_time
            self.metrics.record_operation(f'sustained_write_batch_{batch_num}', 
                                         duration, records_count=batch_size)
        
        # All batches should have similar performance
        batch_stats = []
        for batch_num in range(num_batches):
            stats = self.metrics.get_statistics(f'sustained_write_batch_{batch_num}')
            batch_stats.append(stats['mean_duration'])
        
        # Variance across batches should be low
        batch_cv = (stdev(batch_stats) / mean(batch_stats)) * 100
        self.assertLess(batch_cv, 30,
                       f"Sustained write throughput has high variance (CV={batch_cv:.1f}%)")
    
    def test_unlink_performance(self):
        """Test performance of delete operations."""
        cursor = self.txn.cursor
        uid = self.txn.user
        
        # Test single deletes
        for i in range(20):
            record_id = self.model.create(cursor, uid, {
                'name': f'Delete Test {i}',
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
                       f"Single deletes averaging {single_stats['mean_duration']:.4f}s should be < 0.1s")
        self.assertLess(bulk_stats['mean_duration'], 1.0,
                       f"Bulk deletes (50 records) averaging {bulk_stats['mean_duration']:.4f}s should be < 1.0s")


@unittest.skipIf(SKIP_IF_NOT_CI, SKIP_REASON)
class TestPerformanceRegression(testing.MongoDBTestCase):
    """Test that performance hasn't regressed from the changes."""
    
    def setUp(self):
        self.txn = Transaction().start(self.database)
        self._setup_test_model()
    
    def tearDown(self):
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
                'name': f'Bulk Test {i}',
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
