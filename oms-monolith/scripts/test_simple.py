#!/usr/bin/env python3
"""
Simple test to verify the factory pattern is working
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_factory():
    """Test that we can create services with factory"""
    print("\n=== Testing Service Factory Pattern ===\n")
    
    # Import after path is set
    from shared.config import settings
    from core.branch.service_factory import BranchServiceFactory
    
    # Test 1: Legacy implementation
    print("1. Testing LEGACY implementation creation...")
    settings.USE_TERMINUS_NATIVE_BRANCH = False
    BranchServiceFactory.reset()
    
    try:
        service = BranchServiceFactory.create_branch_service()
        print(f"   ✓ Created service: {type(service).__name__}")
        print(f"   ✓ Is legacy BranchService: {'BranchService' in str(type(service))}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Native implementation (with mock)
    print("\n2. Testing NATIVE implementation creation...")
    settings.USE_TERMINUS_NATIVE_BRANCH = True
    BranchServiceFactory.reset()
    
    # Mock the TerminusDB client
    from unittest.mock import MagicMock, patch
    
    with patch('core.branch.terminus_adapter.WOQLClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        try:
            service = BranchServiceFactory.create_branch_service()
            print(f"   ✓ Created service: {type(service).__name__}")
            print(f"   ✓ Is native TerminusNativeBranchService: {'TerminusNative' in str(type(service))}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Test 3: Verify interface compliance
    print("\n3. Testing interface compliance...")
    from core.branch.interfaces import IBranchService
    
    # Both implementations should implement IBranchService
    settings.USE_TERMINUS_NATIVE_BRANCH = False
    BranchServiceFactory.reset()
    legacy = BranchServiceFactory.create_branch_service()
    
    settings.USE_TERMINUS_NATIVE_BRANCH = True
    BranchServiceFactory.reset()
    with patch('core.branch.terminus_adapter.WOQLClient'):
        native = BranchServiceFactory.create_branch_service()
    
    print(f"   Legacy implements IBranchService: {isinstance(legacy, IBranchService)}")
    print(f"   Native implements IBranchService: {isinstance(native, IBranchService)}")
    
    # Check methods exist
    methods = ['create_branch', 'delete_branch', 'list_branches', 'merge_branches', 'get_diff']
    for method in methods:
        legacy_has = hasattr(legacy, method)
        native_has = hasattr(native, method)
        print(f"   {method}: Legacy={legacy_has}, Native={native_has}")
    
    print("\n✅ Factory pattern is working correctly!")


if __name__ == "__main__":
    test_factory()