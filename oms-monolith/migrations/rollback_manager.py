"""
Rollback Manager for TerminusDB Native Migration
Provides automatic and manual rollback capabilities
"""
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone

from shared.config import settings
from core.branch.service_factory import BranchServiceFactory
from core.merge.factory import MergeEngineFactory
# Merge functionality now handled directly by TerminusDB client
from core.monitoring.migration_monitor import migration_monitor

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manages rollback operations for the migration"""
    
    def __init__(self):
        self.rollback_history = []
        self.health_check_failures = 0
        self.max_failures_before_rollback = 3
        
    async def check_health(self) -> Dict[str, Any]:
        """
        Perform health check on native implementation
        
        Returns:
            Health status and metrics
        """
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy": True,
            "checks": {}
        }
        
        # Check error rates
        progress = migration_monitor.get_migration_progress()
        
        # Check native error rate
        for operation, rates in progress["error_rates"].items():
            native_error_rate = rates.get("native", 0)
            if native_error_rate > 5:  # 5% error threshold
                health_status["healthy"] = False
                health_status["checks"][f"{operation}_error_rate"] = {
                    "status": "unhealthy",
                    "value": native_error_rate,
                    "threshold": 5
                }
            else:
                health_status["checks"][f"{operation}_error_rate"] = {
                    "status": "healthy",
                    "value": native_error_rate
                }
                
        # Check performance degradation
        for operation, times in progress["average_operation_times"].items():
            native_time = times.get("native")
            legacy_time = times.get("legacy")
            
            if native_time and legacy_time:
                degradation = native_time / legacy_time
                if degradation > 2:  # 2x slower threshold
                    health_status["healthy"] = False
                    health_status["checks"][f"{operation}_performance"] = {
                        "status": "unhealthy",
                        "degradation": degradation,
                        "threshold": 2
                    }
                else:
                    health_status["checks"][f"{operation}_performance"] = {
                        "status": "healthy",
                        "degradation": degradation
                    }
                    
        # Test basic operations
        try:
            await self._test_basic_operations()
            health_status["checks"]["basic_operations"] = {"status": "healthy"}
        except Exception as e:
            health_status["healthy"] = False
            health_status["checks"]["basic_operations"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            
        # Track failures
        if not health_status["healthy"]:
            self.health_check_failures += 1
        else:
            self.health_check_failures = 0
            
        health_status["consecutive_failures"] = self.health_check_failures
        
        return health_status
        
    async def _test_basic_operations(self):
        """Test basic native operations work correctly"""
        service = BranchServiceFactory.create_branch_service()
        
        # Test list branches
        branches = await service.list_branches()
        
        # Test create and delete
        test_branch = f"rollback_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        created = await service.create_branch("main", test_branch, "Rollback test")
        await service.delete_branch(created)
        
    def should_auto_rollback(self) -> bool:
        """Determine if automatic rollback should be triggered"""
        # Check consecutive failures
        if self.health_check_failures >= self.max_failures_before_rollback:
            return True
            
        # Check migration monitor recommendation
        should_rollback, _ = migration_monitor.should_rollback()
        return should_rollback
        
    async def rollback_to_legacy(self, reason: str, force: bool = False) -> Dict[str, Any]:
        """
        Rollback to legacy implementation
        
        Args:
            reason: Reason for rollback
            force: Force rollback even if health checks pass
            
        Returns:
            Rollback result
        """
        logger.warning(f"Initiating rollback to legacy: {reason}")
        
        rollback_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "forced": force,
            "previous_settings": {
                "USE_TERMINUS_NATIVE_BRANCH": settings.USE_TERMINUS_NATIVE_BRANCH,
                "USE_UNIFIED_MERGE_ENGINE": settings.USE_UNIFIED_MERGE_ENGINE
            }
        }
        
        try:
            # Disable native implementations
            settings.USE_TERMINUS_NATIVE_BRANCH = False
            settings.USE_UNIFIED_MERGE_ENGINE = False
            
            # Reset factories to use legacy
            BranchServiceFactory.reset()
            MergeEngineFactory.reset()
            
            # Update environment variables for persistence
            os.environ["USE_TERMINUS_NATIVE_BRANCH"] = "false"
            os.environ["USE_UNIFIED_MERGE_ENGINE"] = "false"
            
            # Create checkpoint
            migration_monitor.create_checkpoint(
                "rollback",
                {"reason": reason, "forced": force}
            )
            
            # Test legacy operations
            await self._test_basic_operations()
            
            rollback_record["status"] = "success"
            rollback_record["message"] = "Successfully rolled back to legacy implementation"
            
            logger.info("Rollback completed successfully")
            
        except Exception as e:
            rollback_record["status"] = "failed"
            rollback_record["error"] = str(e)
            logger.error(f"Rollback failed: {e}")
            
        self.rollback_history.append(rollback_record)
        return rollback_record
        
    async def rollforward_to_native(self) -> Dict[str, Any]:
        """
        Roll forward to native implementation after issues are resolved
        
        Returns:
            Rollforward result
        """
        logger.info("Attempting to roll forward to native implementation")
        
        rollforward_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_rollback": self.rollback_history[-1] if self.rollback_history else None
        }
        
        try:
            # Enable native implementations
            settings.USE_TERMINUS_NATIVE_BRANCH = True
            settings.USE_UNIFIED_MERGE_ENGINE = True
            
            # Reset factories
            BranchServiceFactory.reset()
            MergeEngineFactory.reset()
            
            # Update environment
            os.environ["USE_TERMINUS_NATIVE_BRANCH"] = "true"
            os.environ["USE_UNIFIED_MERGE_ENGINE"] = "true"
            
            # Test native operations
            await self._test_basic_operations()
            
            # Perform health check
            health = await self.check_health()
            
            if not health["healthy"]:
                # Rollback again
                await self.rollback_to_legacy(
                    f"Health check failed during rollforward: {health['checks']}"
                )
                rollforward_record["status"] = "failed"
                rollforward_record["reason"] = "Health check failed"
            else:
                rollforward_record["status"] = "success"
                rollforward_record["message"] = "Successfully rolled forward to native"
                
                # Reset failure counter
                self.health_check_failures = 0
                
                # Create checkpoint
                migration_monitor.create_checkpoint("rollforward", health)
                
        except Exception as e:
            rollforward_record["status"] = "failed"
            rollforward_record["error"] = str(e)
            logger.error(f"Rollforward failed: {e}")
            
            # Ensure we're back on legacy
            await self.rollback_to_legacy(f"Rollforward failed: {e}")
            
        return rollforward_record
        
    def get_rollback_status(self) -> Dict[str, Any]:
        """Get current rollback status and history"""
        return {
            "current_implementation": {
                "native_branch": settings.USE_TERMINUS_NATIVE_BRANCH,
                "unified_merge": settings.USE_UNIFIED_MERGE_ENGINE
            },
            "health_check_failures": self.health_check_failures,
            "auto_rollback_threshold": self.max_failures_before_rollback,
            "rollback_history": self.rollback_history,
            "last_rollback": self.rollback_history[-1] if self.rollback_history else None
        }


# Global instance
rollback_manager = RollbackManager()


# CLI Commands
async def rollback_command(reason: str = "Manual rollback", force: bool = False):
    """Command line interface for rollback"""
    result = await rollback_manager.rollback_to_legacy(reason, force)
    
    if result["status"] == "success":
        print("✅ Rollback successful")
        print(f"   Reason: {reason}")
        print("   Implementation: Legacy")
    else:
        print("❌ Rollback failed")
        print(f"   Error: {result.get('error', 'Unknown')}")
        
    return result


async def rollforward_command():
    """Command line interface for rollforward"""
    result = await rollback_manager.rollforward_to_native()
    
    if result["status"] == "success":
        print("✅ Rollforward successful")
        print("   Implementation: Native")
    else:
        print("❌ Rollforward failed")
        print(f"   Reason: {result.get('reason', result.get('error', 'Unknown'))}")
        
    return result


async def health_check_command():
    """Command line interface for health check"""
    health = await rollback_manager.check_health()
    
    print("\n" + "="*50)
    print("MIGRATION HEALTH CHECK")
    print("="*50)
    print(f"Status: {'✅ HEALTHY' if health['healthy'] else '❌ UNHEALTHY'}")
    print(f"Consecutive Failures: {health['consecutive_failures']}")
    print("\nChecks:")
    
    for check_name, check_result in health["checks"].items():
        status_icon = "✅" if check_result["status"] == "healthy" else "❌"
        print(f"  {status_icon} {check_name}: {check_result}")
        
    if rollback_manager.should_auto_rollback():
        print("\n⚠️  AUTO-ROLLBACK RECOMMENDED")
        
    return health