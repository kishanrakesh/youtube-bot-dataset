#!/usr/bin/env python3
"""
Analyze code usage based on Makefile entry points.
Generates call graphs and identifies unused functions/modules.
"""

import ast
import os
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List

# Entry points from Makefile
ENTRY_POINTS = [
    "app.pipeline.trending.fetch",
    "app.pipeline.trending.load",
    "app.pipeline.comments.fetch",
    "app.pipeline.comments.register",
    "app.pipeline.screenshots.capture",
    "app.pipeline.screenshots.review",
]


class CallGraphAnalyzer(ast.NodeVisitor):
    """Extract function calls and imports from Python AST."""
    
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.imports: Dict[str, str] = {}  # alias -> full_name
        self.functions_defined: Set[str] = set()
        self.functions_called: Set[str] = set()
        self.classes_defined: Set[str] = set()
        self.current_function = None
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[name] = alias.name
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                full_name = f"{node.module}.{alias.name}"
                self.imports[name] = full_name
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        self.functions_defined.add(node.name)
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)
        
    def visit_ClassDef(self, node):
        self.classes_defined.add(node.name)
        self.generic_visit(node)
        
    def visit_Call(self, node):
        # Extract function name from call
        if isinstance(node.func, ast.Name):
            self.functions_called.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                self.functions_called.add(f"{node.func.value.id}.{node.func.attr}")
        self.generic_visit(node)


def module_path_to_file(module_name: str) -> Path:
    """Convert module name to file path."""
    parts = module_name.split('.')
    base = Path('.')
    for part in parts:
        base = base / part
    
    # Try .py file first, then __main__.py
    py_file = base.with_suffix('.py')
    if py_file.exists():
        return py_file
    
    init_file = base / '__init__.py'
    if init_file.exists():
        return init_file
    
    main_file = base / '__main__.py'
    if main_file.exists():
        return main_file
        
    return py_file  # Return even if doesn't exist


def analyze_file(file_path: Path) -> CallGraphAnalyzer:
    """Analyze a Python file and return call graph info."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        analyzer = CallGraphAnalyzer(str(file_path))
        analyzer.visit(tree)
        return analyzer
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}")
        return None


def trace_dependencies(entry_point: str, analyzed: Dict[str, CallGraphAnalyzer], 
                       visited: Set[str] = None) -> Set[str]:
    """Recursively trace all dependencies from an entry point."""
    if visited is None:
        visited = set()
    
    if entry_point in visited:
        return visited
    
    visited.add(entry_point)
    
    file_path = module_path_to_file(entry_point)
    if not file_path.exists():
        return visited
    
    if str(file_path) not in analyzed:
        analyzer = analyze_file(file_path)
        if analyzer:
            analyzed[str(file_path)] = analyzer
    
    analyzer = analyzed.get(str(file_path))
    if not analyzer:
        return visited
    
    # Trace imported modules
    for alias, full_name in analyzer.imports.items():
        if full_name.startswith('app.'):
            trace_dependencies(full_name, analyzed, visited)
    
    return visited


def main():
    print("=" * 80)
    print("CALL GRAPH ANALYSIS - Makefile Entry Points")
    print("=" * 80)
    
    analyzed: Dict[str, CallGraphAnalyzer] = {}
    all_used_modules: Set[str] = set()
    
    # Analyze each entry point
    for entry_point in ENTRY_POINTS:
        print(f"\n📍 Entry Point: {entry_point}")
        file_path = module_path_to_file(entry_point)
        print(f"   File: {file_path}")
        
        if not file_path.exists():
            print(f"   ⚠️  File not found!")
            continue
        
        # Trace all dependencies
        used = trace_dependencies(entry_point, analyzed)
        all_used_modules.update(used)
        print(f"   Dependencies: {len(used)} modules")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Collect all app modules
    all_app_files = set()
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py') and file != '__pycache__':
                file_path = Path(root) / file
                all_app_files.add(str(file_path))
    
    used_files = set(analyzed.keys())
    
    print(f"\n📊 Statistics:")
    print(f"   Total Python files in app/: {len(all_app_files)}")
    print(f"   Files analyzed: {len(analyzed)}")
    print(f"   Unique modules used: {len(all_used_modules)}")
    
    # Find potentially unused files
    unused_files = all_app_files - used_files
    if unused_files:
        print(f"\n🗑️  Potentially Unused Files ({len(unused_files)}):")
        for file in sorted(unused_files):
            print(f"   - {file}")
    
    # Generate detailed report
    print("\n" + "=" * 80)
    print("DETAILED CALL GRAPH")
    print("=" * 80)
    
    for entry_point in ENTRY_POINTS:
        print(f"\n{'─' * 80}")
        print(f"📍 {entry_point}")
        print(f"{'─' * 80}")
        
        file_path = str(module_path_to_file(entry_point))
        if file_path in analyzed:
            analyzer = analyzed[file_path]
            
            print(f"\n  Functions Defined ({len(analyzer.functions_defined)}):")
            for func in sorted(analyzer.functions_defined):
                print(f"    ✓ {func}()")
            
            print(f"\n  Direct Imports ({len(analyzer.imports)}):")
            for alias, full_name in sorted(analyzer.imports.items()):
                if full_name.startswith('app.'):
                    print(f"    → {full_name} (as {alias})")
    
    # Save to file
    output_file = "CALL_GRAPH_ANALYSIS.md"
    with open(output_file, 'w') as f:
        f.write("# Call Graph Analysis - Makefile Entry Points\n\n")
        f.write(f"**Generated:** 2025-11-14\n\n")
        f.write("## Entry Points from Makefile\n\n")
        for ep in ENTRY_POINTS:
            f.write(f"- `{ep}`\n")
        
        f.write(f"\n## Statistics\n\n")
        f.write(f"- **Total Python files in app/:** {len(all_app_files)}\n")
        f.write(f"- **Files actually used:** {len(analyzed)}\n")
        f.write(f"- **Potentially unused:** {len(unused_files)}\n")
        
        if unused_files:
            f.write(f"\n## Potentially Unused Files\n\n")
            f.write("These files are not imported by any Makefile entry point:\n\n")
            for file in sorted(unused_files):
                f.write(f"- `{file}`\n")
        
        f.write(f"\n## Dependency Graph\n\n")
        for entry_point in ENTRY_POINTS:
            file_path = str(module_path_to_file(entry_point))
            if file_path in analyzed:
                analyzer = analyzed[file_path]
                f.write(f"\n### {entry_point}\n\n")
                f.write(f"**File:** `{file_path}`\n\n")
                
                if analyzer.functions_defined:
                    f.write(f"**Functions:** {', '.join(sorted(analyzer.functions_defined))}\n\n")
                
                if analyzer.imports:
                    app_imports = [full for full in analyzer.imports.values() if full.startswith('app.')]
                    if app_imports:
                        f.write(f"**Imports:**\n")
                        for imp in sorted(set(app_imports)):
                            f.write(f"- `{imp}`\n")
                        f.write("\n")
    
    print(f"\n✅ Report saved to: {output_file}")


if __name__ == "__main__":
    main()
