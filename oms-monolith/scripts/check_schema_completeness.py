#!/usr/bin/env python
"""
Check if Schema.md requirements are fully implemented
"""
import asyncio
import httpx
import json

# Schema.md에서 정의된 모든 타입들
REQUIRED_SCHEMA_TYPES = [
    "Object Type (객체 타입)",
    "Property (속성)", 
    "Shared Property (공유 속성)",
    "Link Type (링크 타입)",
    "Action Type (액션 타입)",
    "Interface (인터페이스)",
    "Semantic Type (시맨틱 타입)",
    "Struct Type (구조체 타입)"
]

# 구현된 타입 매핑
IMPLEMENTED_MAPPING = {
    "Object Type (객체 타입)": "ObjectType",
    "Property (속성)": "Property",
    "Shared Property (공유 속성)": "SharedProperty",
    "Link Type (링크 타입)": "LinkType",
    "Action Type (액션 타입)": "ActionType",
    "Interface (인터페이스)": "Interface",
    "Semantic Type (시맨틱 타입)": "SemanticType",
    "Struct Type (구조체 타입)": "StructType"
}

# 그래프 기능 요구사항
GRAPH_FEATURES = {
    "링크 타입 정의": {
        "required": ["cardinality", "방향성", "FK 매핑"],
        "implemented": ["cardinality", "sourceObjectType", "targetObjectType"]
    },
    "그래프 인덱스 & 탐색": {
        "required": ["출발-도착 인덱스", "cascade depth", "transitive closure"],
        "implemented": []
    },
    "권한·상태 전파": {
        "required": ["permissionInheritance", "statePropagation"],
        "implemented": []
    },
    "API 스키마 생성": {
        "required": ["GraphQL SDL", "OpenAPI spec", "SingleLink/LinkSet"],
        "implemented": []
    }
}

async def check_schema_implementation():
    """Check actual implementation in TerminusDB"""
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        # Get schema
        response = await client.get('http://localhost:6363/api/schema/admin/oms')
        
        if response.status_code == 200:
            schema = response.json()
            
            print("=" * 80)
            print("SCHEMA.MD COMPLETENESS CHECK")
            print("=" * 80)
            
            # Check schema types
            print("\n## 1. SCHEMA TYPE IMPLEMENTATION\n")
            all_implemented = True
            
            for required_type in REQUIRED_SCHEMA_TYPES:
                impl_name = IMPLEMENTED_MAPPING.get(required_type)
                if impl_name in schema:
                    print(f"✅ {required_type}: IMPLEMENTED as {impl_name}")
                else:
                    print(f"❌ {required_type}: NOT IMPLEMENTED")
                    all_implemented = False
            
            # Check graph features
            print("\n## 2. GRAPH FEATURE IMPLEMENTATION\n")
            
            # Check LinkType schema for graph features
            link_type_schema = schema.get("LinkType", {})
            link_props = [k for k in link_type_schema.keys() if k not in ['@type', '@id', '@key']]
            
            for feature, info in GRAPH_FEATURES.items():
                print(f"### {feature}")
                missing = set(info["required"]) - set(info["implemented"])
                if feature == "링크 타입 정의":
                    # Check if LinkType has required properties
                    if "cardinality" in link_props:
                        print(f"  ✅ Basic structure implemented")
                    else:
                        print(f"  ⚠️  Cardinality not found in LinkType schema")
                elif missing:
                    print(f"  ❌ Missing: {', '.join(missing)}")
                else:
                    print(f"  ✅ All features implemented")
            
            # Check for Data Type (not explicitly in schema)
            print("\n## 3. ADDITIONAL REQUIREMENTS\n")
            print("❓ Data Type (데이터 타입): Handled by TerminusDB's built-in type system")
            print("   - xsd:string, xsd:integer, xsd:boolean etc. are native")
            
            # Summary
            print("\n## 4. SUMMARY\n")
            if all_implemented:
                print("✅ All 8 schema types from Schema.md are implemented!")
            else:
                print("❌ Some schema types are missing")
            
            print("\n⚠️  Graph features need additional implementation:")
            print("   - Graph indexing for efficient traversal")
            print("   - Permission inheritance through links") 
            print("   - State propagation rules")
            print("   - API schema generation (GraphQL/OpenAPI)")
            
            # Check actual data
            print("\n## 5. ACTUAL DATA IN DATABASE\n")
            
            for type_name in ['ObjectType', 'Property', 'LinkType', 'SharedProperty', 'ActionType']:
                response = await client.get(
                    f'http://localhost:6363/api/document/admin/oms',
                    params={'type': type_name}
                )
                
                if response.status_code == 200:
                    count = len(response.text.strip().split('\n')) if response.text.strip() else 0
                    if count > 0:
                        print(f"📊 {type_name}: {count} instances")
                        # Show first few
                        lines = response.text.strip().split('\n')[:3]
                        for line in lines:
                            if line:
                                try:
                                    obj = json.loads(line)
                                    name = obj.get('name', obj.get('@id', 'unnamed'))
                                    print(f"     - {name}")
                                except:
                                    pass
                        if count > 3:
                            print(f"     ... and {count - 3} more")

if __name__ == "__main__":
    asyncio.run(check_schema_implementation())
