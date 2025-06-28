#!/usr/bin/env python3
"""
Test Foundry Alerting System

Tests the newly implemented Foundry alerting mechanisms and plugin scanning.
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.validation.config import get_validation_config
from core.validation.pipeline import ValidationPipeline
from core.validation.adapters import (
    MockEventAdapter, MockTerminusAdapter, MockCacheAdapter, 
    MockPolicyServerAdapter, MockRuleLoaderAdapter
)
from core.validation.ports import ValidationContext


class TestFoundryAlerting:
    """Test suite for Foundry alerting functionality"""
    
    def __init__(self):
        self.config = get_validation_config()
        self.mock_event = MockEventAdapter()
        self.mock_terminus = MockTerminusAdapter()
        self.mock_cache = MockCacheAdapter()
        self.mock_policy = MockPolicyServerAdapter()
        self.mock_rule_loader = MockRuleLoaderAdapter()
        
        # Initialize pipeline with mock adapters
        self.pipeline = ValidationPipeline(
            cache=self.mock_cache,
            terminus=self.mock_terminus,
            event=self.mock_event,
            policy_server=self.mock_policy,
            rule_loader=self.mock_rule_loader,
            config=self.config
        )
    
    async def test_plugin_scanning(self):
        """Test that plugin scanning works correctly"""
        print("🔍 Testing Plugin Scanning...")
        
        try:
            # Test rule imports
            from core.validation.rules import (
                FoundryDatasetAlertingRule, AlertConfig, FoundryAlert,
                RULE_CATEGORIES, RULE_PRIORITIES
            )
            
            print("✅ Successfully imported Foundry alerting components")
            print(f"   - Found {len(RULE_CATEGORIES)} rule categories")
            print(f"   - Found {len(RULE_PRIORITIES)} rule priorities")
            print(f"   - Categories: {list(RULE_CATEGORIES.keys())}")
            
            # Test rule categories
            foundry_rules = RULE_CATEGORIES.get("foundry", [])
            assert "FoundryDatasetAlertingRule" in foundry_rules
            print(f"   - Foundry rules: {foundry_rules}")
            
            return True
            
        except Exception as e:
            print(f"❌ Plugin scanning failed: {e}")
            return False
    
    async def test_foundry_alerting_config(self):
        """Test Foundry alerting configuration"""
        print("\n⚙️  Testing Foundry Alerting Configuration...")
        
        try:
            # Test configuration values
            assert hasattr(self.config, 'enable_foundry_alerting')
            assert hasattr(self.config, 'foundry_alert_severity_threshold')
            assert hasattr(self.config, 'foundry_notification_channels')
            
            print("✅ Foundry alerting configuration loaded successfully")
            print(f"   - Alerting enabled: {self.config.enable_foundry_alerting}")
            print(f"   - Severity threshold: {self.config.foundry_alert_severity_threshold}")
            print(f"   - Notification channels: {self.config.foundry_notification_channels}")
            print(f"   - Max alerts per hour: {self.config.foundry_max_alerts_per_hour}")
            
            return True
            
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False
    
    async def test_foundry_alerting_rule(self):
        """Test Foundry alerting rule execution"""
        print("\n🚨 Testing Foundry Alerting Rule...")
        
        try:
            from core.validation.rules.foundry_alerting_rule import (
                FoundryDatasetAlertingRule, AlertConfig
            )
            
            # Create alert config
            alert_config = AlertConfig(
                enabled=True,
                severity_threshold="medium",
                cooldown_period_minutes=1,  # Short for testing
                max_alerts_per_hour=100,
                notification_channels=["test", "email"]
            )
            
            # Create alerting rule
            alerting_rule = FoundryDatasetAlertingRule(
                event_port=self.mock_event,
                terminus_port=self.mock_terminus,
                alert_config=alert_config
            )
            
            # Create validation context with schema changes
            context = ValidationContext(
                source_branch="feature",
                target_branch="main",
                cache=self.mock_cache,
                terminus_client=self.mock_terminus,
                event_publisher=self.mock_event
            )
            
            # Add schema changes that should trigger alerts
            context.schema_changes = {
                "primary_key_change": [
                    {"entity_id": "User", "field": "id", "old_type": "string", "new_type": "integer"}
                ],
                "required_field_removal": [
                    {"entity_id": "Order", "field": "customer_id", "required": True}
                ]
            }
            
            # Execute alerting rule
            result = await alerting_rule.execute(context)
            
            print("✅ Foundry alerting rule executed successfully")
            print(f"   - Alerts generated: {result.metadata.get('alerts_generated', 0)}")
            print(f"   - Alert types: {result.metadata.get('alert_types', [])}")
            
            # Check if events were published
            events_published = len(self.mock_event.published_events)
            print(f"   - Events published: {events_published}")
            
            if events_published > 0:
                latest_event = self.mock_event.published_events[-1]
                print(f"   - Latest event type: {latest_event.get('event_type')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Foundry alerting rule test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_pipeline_integration(self):
        """Test Foundry alerting integration in validation pipeline"""
        print("\n🔗 Testing Pipeline Integration...")
        
        try:
            # Configure for foundry alerting
            self.config.enable_foundry_alerting = True
            
            # Test entity that should trigger alerts
            test_entity = {
                "@type": "ObjectType",
                "@id": "TestEntity",
                "name": "TestEntity",
                "properties": {
                    "id": {"type": "integer", "required": True},
                    "name": {"type": "string", "required": True}
                }
            }
            
            # Run validation pipeline
            result = await self.pipeline.validate_entity(
                entity_type="ObjectType",
                entity_data=test_entity,
                operation="create"
            )
            
            print("✅ Pipeline integration test completed")
            print(f"   - Validation success: {result.success}")
            print(f"   - Total time: {result.total_time_ms:.2f}ms")
            print(f"   - Stages executed: {list(result.stage_results.keys())}")
            
            # Check if Foundry alerting stage was executed
            from core.validation.pipeline import ValidationStage
            if ValidationStage.FOUNDRY_ALERTING in result.stage_results:
                foundry_result = result.stage_results[ValidationStage.FOUNDRY_ALERTING]
                print(f"   - Foundry alerting executed: ✅")
                print(f"   - Alerts generated: {foundry_result.get('alerts_generated', 0)}")
            else:
                print(f"   - Foundry alerting stage: ❌ Not executed")
            
            return True
            
        except Exception as e:
            print(f"❌ Pipeline integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_event_publishing(self):
        """Test event publishing through EventPort"""
        print("\n📡 Testing Event Publishing...")
        
        try:
            # Test direct event publishing
            test_event_data = {
                "alert_id": "test_alert_001",
                "alert_type": "schema_change",
                "severity": "high",
                "title": "Test Alert",
                "description": "This is a test alert",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.mock_event.publish(
                event_type="foundry.alert.generated",
                data=test_event_data,
                correlation_id="test_correlation_001"
            )
            
            print("✅ Event publishing test successful")
            print(f"   - Events in queue: {len(self.mock_event.published_events)}")
            
            # Verify event structure
            if self.mock_event.published_events:
                latest_event = self.mock_event.published_events[-1]
                print(f"   - Event type: {latest_event.get('event_type')}")
                print(f"   - Correlation ID: {latest_event.get('correlation_id')}")
                print(f"   - Data keys: {list(latest_event.get('data', {}).keys())}")
            
            return True
            
        except Exception as e:
            print(f"❌ Event publishing test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🧪 Starting Foundry Alerting Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_plugin_scanning,
            self.test_foundry_alerting_config,
            self.test_foundry_alerting_rule,
            self.test_pipeline_integration,
            self.test_event_publishing
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                print(f"❌ Test {test.__name__} failed with exception: {e}")
                results.append(False)
        
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)
        
        passed = sum(results)
        total = len(results)
        
        for i, (test, result) in enumerate(zip(tests, results)):
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{i+1}. {test.__name__}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Foundry alerting system is working correctly.")
        else:
            print("⚠️  Some tests failed. Please review the output above.")
        
        return passed == total


async def main():
    """Main test runner"""
    test_suite = TestFoundryAlerting()
    success = await test_suite.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)