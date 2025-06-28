#!/usr/bin/env python
"""
Compare Schema.md requirements with actual TerminusDB implementation
"""
import asyncio
import httpx
import json
from typing import Dict, List, Set

# Schema.md에서 정의된 타입들
REQUIRED_TYPES = {
    "Object Type": {
        "description": "현실 세계의 개체나 사건을 표현하는 온톨로지 스키마",
        "required_properties": ["name", "displayName", "description"],
        "implemented_as": "ObjectType"
    },
    "Property": {
        "description": "객체 타입이 가지는 특성(attribute)",
        "required_properties": ["name", "displayName", "description", "dataType", "objectType", "required", "indexed"],
        "implemented_as": "Property"
    },
    "Shared Property": {
        "description": "여러 객체 타입에서 공통적으로 활용할 수 있는 속성",
        "required_properties": ["name", "displayName", "description", "dataType"],
        "implemented_as": "SharedProperty"  # To be implemented
    },
    "Link Type": {
        "description": "두 객체 타입 간의 관계를 정의",
        "required_properties": ["name", "displayName", "description", "sourceObjectType", "targetObjectType", "cardinality"],
        "implemented_as": "LinkType"
    },
    "Action Type": {
        "description": "객체, 속성, 링크에 대한 변경 작업 정의",
        "required_properties": ["name", "displayName", "description", "targetTypes", "operations"],
        "implemented_as": "ActionType"  # To be implemented
    },
    "Interface": {
        "description": "여러 객체 타입에 공통되는 속성 구조와 동작",
        "required_properties": ["name", "displayName", "description", "properties", "actions"],
        "implemented_as": "Interface"  # To be implemented
    },
    "Semantic Type": {
        "description": "기본 데이터 타입에 의미론적 메타데이터와 제약을 부가",
        "required_properties": ["name", "baseType", "constraints", "description"],
        "implemented_as": "SemanticType"  # To be implemented
    },
    "Struct Type": {
        "description": "다중 필드로 구성된 복합 속성",
        "required_properties": ["name", "fields", "description"],
        "implemented_as": "StructType"  # To be implemented
    }
}

# 그래프 기능 요구사항
GRAPH_FEATURES = {
    "Link Type Definition": {
        "requirements": ["cardinality", "directionality", "FK mapping"],
        "status": "Partially Implemented"
    },
    "Graph Index & Navigation": {
        "requirements": ["source-target index", "cascade depth", "transitive closure"],
        "status": "Not Implemented"
    },
    "Permission & State Propagation": {
        "requirements": ["permissionInheritance", "statePropagation"],
        "status": "Not Implemented"
    },
    "API Schema Generation": {
        "requirements": ["GraphQL SDL", "OpenAPI spec", "SingleLink/LinkSet types"],
        "status": "Not Implemented"
    }
}

async def check_terminus_schema():
    """Check what's actually implemented in TerminusDB"""
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        # Get current schema
        response = await client.get('http://localhost:6363/api/schema/admin/oms')
        
        if response.status_code == 200:
            schema = response.json()
            implemented = {}
            
            # Check each schema class
            for key, value in schema.items():
                if key not in ['@context', '@type'] and isinstance(value, dict):
                    if value.get('@type') == 'Class':
                        properties = []
                        for prop_key, prop_value in value.items():
                            if prop_key not in ['@type', '@id', '@key']:
                                properties.append(prop_key)
                        
                        implemented[key] = {
                            "type": "Class",
                            "properties": properties
                        }
            
            return implemented
        return {}

async def check_existing_data():
    """Check what data exists in TerminusDB"""
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        data_counts = {}
        
        for type_name in ['ObjectType', 'Property', 'LinkType']:
            response = await client.get(
                f'http://localhost:6363/api/document/admin/oms',
                params={'type': type_name}
            )
            
            if response.status_code == 200:
                count = len(response.text.strip().split('\n')) if response.text.strip() else 0
                data_counts[type_name] = count
        
        return data_counts

def generate_implementation_report(implemented_schema, data_counts):
    """Generate a comparison report"""
    print("=" * 80)
    print("SCHEMA IMPLEMENTATION COMPARISON REPORT")
    print("=" * 80)
    
    print("\n## 1. SCHEMA TYPE IMPLEMENTATION STATUS\n")
    
    implemented_types = set(implemented_schema.keys())
    
    for req_type, req_info in REQUIRED_TYPES.items():
        impl_name = req_info["implemented_as"]
        
        if impl_name in implemented_types:
            status = "✅ IMPLEMENTED"
            impl_props = implemented_schema[impl_name]["properties"]
            missing_props = set(req_info["required_properties"]) - set(impl_props)
            
            print(f"### {req_type}")
            print(f"Status: {status}")
            print(f"Description: {req_info['description']}")
            print(f"Implementation: {impl_name}")
            
            if missing_props:
                print(f"⚠️  Missing properties: {', '.join(missing_props)}")
            else:
                print(f"✅ All required properties present")
            
            if impl_name in data_counts:
                print(f"📊 Data count: {data_counts[impl_name]} instances")
        else:
            print(f"### {req_type}")
            print(f"Status: ❌ NOT IMPLEMENTED")
            print(f"Description: {req_info['description']}")
            print(f"Expected implementation: {impl_name}")
        
        print()
    
    print("\n## 2. GRAPH FEATURES STATUS\n")
    
    for feature, info in GRAPH_FEATURES.items():
        print(f"### {feature}")
        print(f"Status: {info['status']}")
        print(f"Requirements: {', '.join(info['requirements'])}")
        print()
    
    print("\n## 3. IMPLEMENTATION GAPS\n")
    
    not_implemented = []
    for req_type, req_info in REQUIRED_TYPES.items():
        if req_info["implemented_as"] not in implemented_types:
            not_implemented.append(req_type)
    
    if not_implemented:
        print("The following types are NOT implemented:")
        for typ in not_implemented:
            print(f"  - {typ} ({REQUIRED_TYPES[typ]['implemented_as']})")
    else:
        print("✅ All basic types are implemented!")
    
    print("\n## 4. RECOMMENDATIONS\n")
    
    print("1. **Immediate priorities:**")
    print("   - Implement SharedProperty for reusable property definitions")
    print("   - Add ActionType for business operations")
    print("   - Create Interface type for polymorphism")
    print()
    print("2. **Schema enhancements:**")
    print("   - Add validation constraints to properties")
    print("   - Implement cardinality constraints on LinkTypes")
    print("   - Add metadata fields for audit/governance")
    print()
    print("3. **Graph features:**")
    print("   - Implement graph indexing for efficient traversal")
    print("   - Add permission inheritance through links")
    print("   - Enable GraphQL/OpenAPI generation from schema")

async def main():
    """Run the comparison"""
    print("Checking TerminusDB schema implementation...")
    
    # Get current implementation
    implemented_schema = await check_terminus_schema()
    data_counts = await check_existing_data()
    
    # Generate report
    generate_implementation_report(implemented_schema, data_counts)
    
    # Save report
    report = {
        "implemented_schema": implemented_schema,
        "data_counts": data_counts,
        "required_types": list(REQUIRED_TYPES.keys()),
        "implementation_gaps": [
            typ for typ, info in REQUIRED_TYPES.items()
            if info["implemented_as"] not in implemented_schema
        ]
    }
    
    with open('schema_implementation_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n✅ Report saved to schema_implementation_report.json")

if __name__ == "__main__":
    asyncio.run(main())