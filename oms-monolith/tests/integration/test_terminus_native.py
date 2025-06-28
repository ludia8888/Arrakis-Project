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
from shared.exceptions import NotFoundError


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
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset factory after each test"""
        yield
        BranchServiceFactory.reset()
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("use_native", [True, False])
    async def test_branch_creation_compatibility(self, use_native):
        """Test branch creation works with both implementations"""
        # Set feature flag
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', use_native):
            service = get_branch_service()
            
            # Mock TerminusDB client if using native
            if use_native:
                with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.create_branch.return_value = True
                    mock_client.insert_document.return_value = True
                    mock_client_class.return_value = mock_client
                    
                    # Reinitialize service to use mock
                    BranchServiceFactory.reset()
                    service = get_branch_service()
                    
                    # Create branch
                    branch_name = await service.create_branch("main", "test-feature", "Test branch")
                    
                    # Verify TerminusDB native create_branch was called
                    assert mock_client.create_branch.called
                    assert "proposal_test-feature" in branch_name
            else:
                # For legacy, we'd need to mock the legacy dependencies
                # This is a placeholder - actual test would need proper mocks
                pass
    
    @pytest.mark.asyncio
    async def test_merge_result_format_consistency(self, mock_terminus_client):
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
    async def test_diff_format_compatibility(self, mock_terminus_client):
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
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset factory after each test"""
        yield
        BranchServiceFactory.reset()
    
    @pytest.mark.asyncio
    async def test_service_creation_tracking(self):
        """Test that we can track which implementation is being used"""
        implementations_used = []
        
        # Since legacy code is removed, we always get native implementation
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', False):
            with patch('core.branch.terminus_adapter.WOQLClient'):
                service = get_branch_service()
                implementations_used.append(type(service).__name__)
        
        BranchServiceFactory.reset()
        
        # Test with native enabled
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient'):
                service = get_branch_service()
                implementations_used.append(type(service).__name__)
        
        # Now all implementations should be native
        assert all(impl == 'TerminusNativeBranchService' for impl in implementations_used)
        assert len(implementations_used) == 2


class TestErrorHandling:
    """Test error handling in native implementation"""
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset factory after each test"""
        yield
        BranchServiceFactory.reset()
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self):
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


class TestBranchListingAndInfo:
    """Test branch listing and information retrieval"""
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset factory after each test"""
        yield
        BranchServiceFactory.reset()
    
    @pytest.fixture
    def mock_terminus_client_with_branches(self):
        """Mock TerminusDB client with branch data"""
        mock_client = MagicMock()
        
        # Mock list_branches API
        mock_client.list_branches.return_value = ['main', 'proposal_feature_20240101_120000']
        
        # Mock WOQL query response
        mock_client.query.return_value = {
            'bindings': [
                {'Name': {'@value': 'main'}},
                {'Name': {'@value': 'proposal_feature_20240101_120000'}}
            ]
        }
        
        return mock_client
    
    @pytest.mark.asyncio
    async def test_list_branches_api_success(self, mock_terminus_client_with_branches):
        """Test list_branches when API call succeeds"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client_class.return_value = mock_terminus_client_with_branches
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                branches = await service.list_branches()
                
                # Verify results
                assert len(branches) == 2
                assert any(b['name'] == 'main' for b in branches)
                assert any(b['name'] == 'proposal_feature_20240101_120000' for b in branches)
                
                # Verify structure
                for branch in branches:
                    assert 'name' in branch
                    assert 'head' in branch
                    assert 'timestamp' in branch
    
    @pytest.mark.asyncio
    async def test_list_branches_api_fails_woql_succeeds(self):
        """Test list_branches when API fails but WOQL succeeds"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client = MagicMock()
                
                # API fails
                mock_client.list_branches.side_effect = AttributeError("list_branches not found")
                mock_client.get_all_branches.side_effect = AttributeError("get_all_branches not found")
                
                # WOQL succeeds
                mock_client.query.return_value = {
                    'bindings': [
                        {'Name': {'@value': 'main'}},
                        {'Name': 'feature_branch'}  # Test different binding format
                    ]
                }
                
                mock_client_class.return_value = mock_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                branches = await service.list_branches()
                
                # Verify WOQL fallback worked
                assert len(branches) == 2
                assert any(b['name'] == 'main' for b in branches)
                assert any(b['name'] == 'feature_branch' for b in branches)
    
    @pytest.mark.asyncio
    async def test_list_branches_complete_failure_fallback(self):
        """Test list_branches when both API and WOQL fail"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client = MagicMock()
                
                # Both methods fail
                mock_client.list_branches.side_effect = Exception("API failed")
                mock_client.query.side_effect = Exception("WOQL failed")
                
                mock_client_class.return_value = mock_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                branches = await service.list_branches()
                
                # Verify fallback to main branch
                assert len(branches) == 1
                assert branches[0]['name'] == 'main'
                assert branches[0]['head'] is None
                assert branches[0]['timestamp'] is None
    
    @pytest.mark.asyncio
    async def test_list_branches_duplicate_removal(self):
        """Test that duplicate branches are removed"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client = MagicMock()
                
                # API returns duplicates
                mock_client.list_branches.return_value = ['main', 'feature', 'main']
                
                mock_client_class.return_value = mock_client
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                branches = await service.list_branches()
                
                # Verify no duplicates
                branch_names = [b['name'] for b in branches]
                assert len(branch_names) == len(set(branch_names))
                assert 'main' in branch_names
                assert 'feature' in branch_names
    
    @pytest.mark.asyncio
    async def test_get_branch_info_existing_branch(self, mock_terminus_client_with_branches):
        """Test getting info for existing branch"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                # Add metadata mock
                mock_terminus_client_with_branches.get_document.return_value = {
                    'description': 'Main branch',
                    'created_by': 'admin'
                }
                
                mock_client_class.return_value = mock_terminus_client_with_branches
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                branch_info = await service.get_branch_info('main')
                
                # Verify branch info structure
                assert branch_info['name'] == 'main'
                assert 'head' in branch_info
                assert 'timestamp' in branch_info
                # Metadata should be merged
                assert 'description' in branch_info
                assert 'created_by' in branch_info
    
    @pytest.mark.asyncio
    async def test_get_branch_info_nonexistent_branch(self, mock_terminus_client_with_branches):
        """Test getting info for non-existent branch raises NotFoundError"""
        with patch.object(settings, 'USE_TERMINUS_NATIVE_BRANCH', True):
            with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
                mock_client_class.return_value = mock_terminus_client_with_branches
                
                BranchServiceFactory.reset()
                service = get_branch_service()
                
                # Should raise NotFoundError
                with pytest.raises(NotFoundError) as exc_info:
                    await service.get_branch_info('nonexistent_branch')
                
                assert 'nonexistent_branch not found' in str(exc_info.value)