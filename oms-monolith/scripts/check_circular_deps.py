#!/usr/bin/env python3
"""
Check for circular dependencies in Python code using Tarjan's algorithm
"""
import os
import ast
import sys
import json
from pathlib import Path
from typing import Dict, Set, List

def get_python_files(workspace: str = '.') -> List[str]:
    """Find all Python files in workspace"""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        # Skip virtual environments and caches
        if any(skip in dirpath for skip in ['.git', '__pycache__', '.venv', 'venv', '.ruff_cache', '.pytest_cache']):
            continue
        for fname in filenames:
            if fname.endswith('.py'):
                py_files.append(os.path.join(dirpath, fname))
    return py_files

def build_import_graph(py_files: List[str], workspace: str = '.') -> Dict[str, Set[str]]:
    """Build import dependency graph"""
    # Map file paths to module names
    module_names = {}
    for f in py_files:
        rel = os.path.relpath(f, workspace)
        module = rel[:-3].replace(os.sep, '.')
        module_names[f] = module
    
    # Build edges
    edges = {}
    for f in py_files:
        src_mod = module_names[f]
        edges[src_mod] = set()
        
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                tree = ast.parse(fh.read(), filename=f)
        except SyntaxError:
            continue
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges[src_mod].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                level = node.level
                mod = node.module
                if level == 0:
                    edges[src_mod].add(mod)
                else:
                    # Handle relative imports
                    parts = src_mod.split('.')
                    base = parts[:-level]
                    mod_full = '.'.join(base + ([mod] if mod else []))
                    edges[src_mod].add(mod_full)
    
    # Filter to internal modules only
    internal_modules = set(edges.keys())
    for src in list(edges.keys()):
        new_targets = set()
        for tgt in edges[src]:
            for im in internal_modules:
                if tgt == im or tgt.startswith(im + '.'):
                    new_targets.add(im)
                    break
        edges[src] = new_targets
    
    return edges, internal_modules

def find_sccs(edges: Dict[str, Set[str]], internal_modules: Set[str]) -> List[List[str]]:
    """Find strongly connected components using Tarjan's algorithm"""
    index = 0
    stack = []
    indices = {}
    lowlink = {}
    result = []
    onstack = set()
    
    def strongconnect(v):
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)
        
        for w in edges.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], indices[w])
        
        if lowlink[v] == indices[v]:
            scc = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                result.append(sorted(scc))
    
    for v in internal_modules:
        if v not in indices:
            strongconnect(v)
    
    return result

def main():
    """Main function"""
    workspace = '.'
    py_files = get_python_files(workspace)
    edges, internal_modules = build_import_graph(py_files, workspace)
    sccs = find_sccs(edges, internal_modules)
    
    if sccs:
        print("CIRCULAR DEPENDENCIES DETECTED!")
        print("=" * 60)
        for i, scc in enumerate(sccs, 1):
            print(f"\nCircular dependency #{i}:")
            for module in scc:
                print(f"  - {module}")
        print(f"\nTotal circular dependencies: {len(sccs)}")
        return 1
    else:
        print("No circular dependencies found ✓")
        return 0

if __name__ == "__main__":
    sys.exit(main())