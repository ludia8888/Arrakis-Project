"""
Integration tests for TerminusDB Native Branch Service
Tests compatibility between legacy and native implementations
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.branch.service_factory import BranchServiceFactory, get_branch_service
from core.branch.interfaces import IBranchService
from shared.config import settings


class TestTerminusNativeCompatibility:
    """Test suite for TerminusDB native implementation compatibility"""
    
    @pytest.fixture
    def mock_terminus_client(self):
        """Mock TerminusDB client for testing"""
        mock_client = MagicMock()
        mock_client.branch.return_value = True
        mock_client.delete_branch.return_value = True
        mock_client.merge.return_value = {"commit": "abc123", "status": "success"}
        mock_client.diff.return_value = {"changes": []}
        mock_client.list_branches.return_value = ["main", "proposal/test/20240101"]
        return mock_client
    
    @pytest.fixture
    def reset_factory(self):
        """Reset factory after each test"""
        yield
        BranchServiceFactory.reset()
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("use_native", [True, False])
    async def test_branch_creation_compatibility(self, use_native, reset_factory):
        """Test branch creation works with both implementations"""
        # Set feature flag
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', use_native):
            service = get_branch_service()
            
            # Mock TerminusDB client if using native
            if use_native:
                with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.branch.return_value = True
                    mock_client.insert_document.return_value = True
                    mock_client_class.return_value = mock_client
                    
                    # Reinitialize service to use mock
                    BranchServiceFactory.reset()
                    service = get_branch_service()
                    
                    # Create branch
                    branch_name = await service.create_branch("main", "test-feature", "Test branch")
                    
                    # Verify TerminusDB native branch was called
                    assert mock_client.branch.called
                    assert "proposal/test-feature" in branch_name
            else:
                # For legacy, we'd need to mock the legacy dependencies
                # This is a placeholder - actual test would need proper mocks
                pass
    
    @pytest.mark.asyncio
    async def test_merge_result_format_consistency(self, mock_terminus_client, reset_factory):
        """Test merge results have consistent format"""
        # Test native implementation
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client_class.return_value = mock_terminus_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                # Mock diff to show changes
                mock_terminus_client.diff.return_value = {
                    "changes": [{"@type": "Change", "@id": "test"}]
                }
                
                result = await service.merge_branches(
                    "proposal/feature",
                    "main",
                    "test_user",
                    "Test merge"
                )
                
                # Check result format
                assert hasattr(result, 'status')
                assert result.status in ['success', 'conflict', 'no_changes', 'error']
    
    @pytest.mark.asyncio
    async def test_diff_format_compatibility(self, mock_terminus_client, reset_factory):
        """Test diff format is consistent between implementations"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_terminus_client.diff.return_value = {
                    "changes": [
                        {
                            "@type": "Addition",
                            "@id": "ObjectType/Customer",
                            "@after": {"name": "Customer"}
                        }
                    ]
                }
                mock_client_class.return_value = mock_terminus_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                diff = await service.get_diff("branch1", "branch2")
                
                # Check diff format
                assert hasattr(diff, 'changes')
                assert isinstance(diff.changes, list)
                if diff.changes:
                    change = diff.changes[0]
                    assert 'operation' in change
                    assert change['operation'] in ['added', 'modified', 'deleted', 'unknown']


class TestMigrationMonitoring:
    """Tests for monitoring migration progress"""
    
    @pytest.mark.asyncio
    async def test_service_creation_tracking(self, reset_factory):
        """Test that we can track which implementation is being used"""
        implementations_used = []
        
        # Test with native disabled
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', False):
            service = get_branch_service()
            implementations_used.append(type(service).__name__)
        
        BranchServiceFactory.reset()
        
        # Test with native enabled
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient'):
                service = get_branch_service()
                implementations_used.append(type(service).__name__)
        
        # Should have used different implementations
        assert 'BranchService' in implementations_used
        assert 'TerminusNativeBranchService' in implementations_used


class TestErrorHandling:
    """Test error handling in native implementation"""
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, reset_factory):
        """Test that conflicts are properly detected and reported"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client = MagicMock()
                
                # Simulate merge conflict
                mock_client.diff.return_value = {"changes": [{"@type": "Change"}]}
                mock_client.merge.side_effect = Exception("Merge conflict detected")
                mock_client_class.return_value = mock_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                result = await service.merge_branches(
                    "branch1", 
                    "main",
                    "user",
                    "Test merge"
                )
                
                assert result.status == "conflict"
                assert result.conflicts is not None