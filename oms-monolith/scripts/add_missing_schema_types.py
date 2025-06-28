#!/usr/bin/env python
"""
Add missing schema types to TerminusDB based on Schema.md requirements
"""
import asyncio
import httpx
import json

MISSING_SCHEMA_TYPES = [
    {
        "@type": "Class",
        "@id": "SharedProperty",
        "@key": {"@type": "Lexical", "@fields": ["name"]},
        "name": "xsd:string",
        "displayName": "xsd:string",
        "description": "xsd:string",
        "dataType": "xsd:string",
        "constraints": {"@type": "Optional", "@class": "xsd:string"},
        "defaultValue": {"@type": "Optional", "@class": "xsd:string"}
    },
    {
        "@type": "Class",
        "@id": "ActionType",
        "@key": {"@type": "Lexical", "@fields": ["name"]},
        "name": "xsd:string",
        "displayName": "xsd:string",
        "description": "xsd:string",
        "targetTypes": {"@type": "Set", "@class": "ObjectType"},
        "operations": {"@type": "List", "@class": "xsd:string"},
        "sideEffects": {"@type": "Optional", "@class": "xsd:string"},
        "permissions": {"@type": "Optional", "@class": "xsd:string"}
    },
    {
        "@type": "Class",
        "@id": "Interface",
        "@key": {"@type": "Lexical", "@fields": ["name"]},
        "name": "xsd:string",
        "displayName": "xsd:string", 
        "description": "xsd:string",
        "properties": {"@type": "Set", "@class": "Property"},
        "sharedProperties": {"@type": "Set", "@class": "SharedProperty"},
        "actions": {"@type": "Set", "@class": "ActionType"}
    },
    {
        "@type": "Class",
        "@id": "SemanticType",
        "@key": {"@type": "Lexical", "@fields": ["name"]},
        "name": "xsd:string",
        "displayName": "xsd:string",
        "description": "xsd:string",
        "baseType": "xsd:string",
        "constraints": {"@type": "Optional", "@class": "xsd:string"},
        "validationRules": {"@type": "List", "@class": "xsd:string"},
        "examples": {"@type": "List", "@class": "xsd:string"}
    },
    {
        "@type": "Class",
        "@id": "StructType",
        "@key": {"@type": "Lexical", "@fields": ["name"]},
        "name": "xsd:string",
        "displayName": "xsd:string",
        "description": "xsd:string",
        "fields": {"@type": "List", "@class": "StructField"}
    },
    {
        "@type": "Class",
        "@id": "StructField",
        "@key": {"@type": "Lexical", "@fields": ["structType", "name"]},
        "name": "xsd:string",
        "displayName": "xsd:string",
        "fieldType": "xsd:string",
        "required": "xsd:boolean",
        "structType": "StructType"
    }
]

# Graph enhancement properties
GRAPH_ENHANCEMENTS = {
    "LinkType": {
        "permissionInheritance": {"@type": "Optional", "@class": "xsd:boolean"},
        "statePropagation": {"@type": "Optional", "@class": "xsd:boolean"},
        "cascadeDepth": {"@type": "Optional", "@class": "xsd:integer"},
        "transitiveClosureEnabled": {"@type": "Optional", "@class": "xsd:boolean"}
    }
}

async def add_missing_types():
    """Add missing schema types to TerminusDB"""
    print("Adding missing schema types to TerminusDB...")
    
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        # Add missing types
        response = await client.post(
            'http://localhost:6363/api/document/admin/oms',
            json=MISSING_SCHEMA_TYPES,
            params={
                'graph_type': 'schema',
                'author': 'schema_upgrade',
                'message': 'Add missing schema types from Schema.md'
            }
        )
        
        if response.status_code == 200:
            print("✅ Successfully added missing schema types!")
        else:
            print(f"❌ Failed to add schema types: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Verify the additions
        verify_response = await client.get(
            'http://localhost:6363/api/schema/admin/oms'
        )
        
        if verify_response.status_code == 200:
            schema = verify_response.json()
            print("\n✅ Updated schema now includes:")
            for key in schema:
                if key not in ['@context', '@type']:
                    print(f"  - {key}")
        
        return True

async def create_sample_shared_properties():
    """Create sample SharedProperty instances"""
    print("\nCreating sample SharedProperty instances...")
    
    shared_properties = [
        {
            "@type": "SharedProperty",
            "@id": "SharedProperty/Email",
            "name": "email",
            "displayName": "Email Address",
            "description": "Standard email address property",
            "dataType": "xsd:string",
            "constraints": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        },
        {
            "@type": "SharedProperty",
            "@id": "SharedProperty/PhoneNumber",
            "name": "phoneNumber",
            "displayName": "Phone Number",
            "description": "Standard phone number property",
            "dataType": "xsd:string",
            "constraints": "^\\+?[1-9]\\d{1,14}$"
        },
        {
            "@type": "SharedProperty",
            "@id": "SharedProperty/URL",
            "name": "url",
            "displayName": "URL",
            "description": "Standard URL property",
            "dataType": "xsd:string",
            "constraints": "^https?:\\/\\/(www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b([-a-zA-Z0-9()@:%_\\+.~#?&//=]*)$"
        }
    ]
    
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        response = await client.post(
            'http://localhost:6363/api/document/admin/oms',
            json=shared_properties,
            params={
                'author': 'schema_demo',
                'message': 'Create sample shared properties'
            }
        )
        
        if response.status_code == 200:
            print("✅ Created sample SharedProperty instances")
        else:
            print(f"❌ Failed to create SharedProperty instances: {response.text}")

async def create_sample_action_type():
    """Create a sample ActionType"""
    print("\nCreating sample ActionType...")
    
    action_type = {
        "@type": "ActionType",
        "@id": "ActionType/ApproveOrder",
        "name": "ApproveOrder",
        "displayName": "Approve Order",
        "description": "Action to approve a pending order",
        "targetTypes": ["ObjectType/Order"],
        "operations": [
            "set:status=approved",
            "set:approvedAt=now()",
            "set:approvedBy=currentUser()"
        ],
        "sideEffects": "notify:customer,notify:warehouse",
        "permissions": "role:manager,role:admin"
    }
    
    async with httpx.AsyncClient(auth=('admin', 'root')) as client:
        response = await client.post(
            'http://localhost:6363/api/document/admin/oms',
            json=[action_type],
            params={
                'author': 'schema_demo',
                'message': 'Create sample action type'
            }
        )
        
        if response.status_code == 200:
            print("✅ Created sample ActionType")
        else:
            print(f"❌ Failed to create ActionType: {response.text}")

async def main():
    """Main execution"""
    print("=" * 60)
    print("ADDING MISSING SCHEMA TYPES")
    print("=" * 60)
    
    # Add missing types to schema
    success = await add_missing_types()
    
    if success:
        # Create sample instances
        await create_sample_shared_properties()
        await create_sample_action_type()
        
        print("\n" + "=" * 60)
        print("✅ Schema upgrade completed!")
        print("=" * 60)
    else:
        print("\n❌ Schema upgrade failed")

if __name__ == "__main__":
    asyncio.run(main())