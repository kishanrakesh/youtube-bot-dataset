#!/usr/bin/env python3
"""
Deep dependency analysis using modulegraph to find ALL code used by Makefile entry points.
"""

import sys
import os
from pathlib import Path
from modulegraph.modulegraph import ModuleGraph

# Entry points from Makefile
ENTRY_POINTS = [
    "app/pipeline/trending/fetch.py",
    "app/pipeline/trending/load.py",
    "app/pipeline/comments/fetch.py",
    "app/pipeline/comments/register.py",
    "app/pipeline/screenshots/capture.py",
    "app/pipeline/screenshots/review.py",
]

def main():
    print("=" * 80)
    print("DEEP DEPENDENCY ANALYSIS - Makefile Entry Points")
    print("=" * 80)
    
    # Create module graph
    mg = ModuleGraph(path=[os.getcwd()] + sys.path)
    
    # Analyze each entry point
    for entry_point in ENTRY_POINTS:
        print(f"\n📍 Analyzing: {entry_point}")
        if Path(entry_point).exists():
            mg.run_script(entry_point)
        else:
            print(f"   ⚠️  File not found!")
    
    # Get all modules used
    app_modules = set()
    all_modules = set()
    
    for node in mg.flatten():
        module_name = node.identifier
        all_modules.add(module_name)
        
        # Track app.* modules
        if module_name and module_name.startswith('app.'):
            app_modules.add(module_name)
            
        # Track files in app/ directory
        if hasattr(node, 'filename') and node.filename:
            if 'app/' in node.filename and node.filename.endswith('.py'):
                rel_path = node.filename
                if os.getcwd() in node.filename:
                    rel_path = node.filename.replace(os.getcwd() + '/', '')
                app_modules.add(rel_path)
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    print(f"\n📊 Modules Found:")
    print(f"   Total modules imported: {len(all_modules)}")
    print(f"   App modules used: {len(app_modules)}")
    
    # Find all Python files in app/
    all_app_files = []
    for root, dirs, files in os.walk('app'):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                all_app_files.append(file_path)
    
    # Convert module names to file paths for comparison
    used_files = set()
    for mod in app_modules:
        if mod.endswith('.py'):
            used_files.add(mod)
        else:
            # Convert module name to file path
            parts = mod.split('.')
            # Try both module.py and module/__init__.py
            py_file = '/'.join(parts) + '.py'
            init_file = '/'.join(parts) + '/__init__.py'
            
            if Path(py_file).exists():
                used_files.add(py_file)
            if Path(init_file).exists():
                used_files.add(init_file)
    
    unused_files = set(all_app_files) - used_files
    
    print(f"\n📁 File Analysis:")
    print(f"   Total Python files in app/: {len(all_app_files)}")
    print(f"   Files actually used: {len(used_files)}")
    print(f"   Potentially unused: {len(unused_files)}")
    
    if unused_files:
        print(f"\n🗑️  Potentially UNUSED Files:")
        for file in sorted(unused_files):
            print(f"   - {file}")
    
    print(f"\n✅ USED Files ({len(used_files)}):")
    for file in sorted(used_files):
        print(f"   ✓ {file}")
    
    # Save detailed report
    with open('CALL_GRAPH_ANALYSIS.md', 'w') as f:
        f.write("# Deep Dependency Analysis - Makefile Entry Points\n\n")
        f.write("**Generated:** 2025-11-14  \n")
        f.write("**Tool:** modulegraph (deep analysis)\n\n")
        
        f.write("## Entry Points\n\n")
        for ep in ENTRY_POINTS:
            f.write(f"- `{ep}`\n")
        
        f.write(f"\n## Summary\n\n")
        f.write(f"- **Total Python files in app/:** {len(all_app_files)}\n")
        f.write(f"- **Files actually USED:** {len(used_files)}\n")
        f.write(f"- **Files potentially UNUSED:** {len(unused_files)}\n")
        f.write(f"- **Usage rate:** {len(used_files)/len(all_app_files)*100:.1f}%\n")
        
        f.write(f"\n## ✅ Used Files ({len(used_files)})\n\n")
        f.write("These files are imported (directly or indirectly) by Makefile entry points:\n\n")
        for file in sorted(used_files):
            f.write(f"- `{file}`\n")
        
        if unused_files:
            f.write(f"\n## 🗑️ Potentially Unused Files ({len(unused_files)})\n\n")
            f.write("These files are NOT imported by any Makefile entry point and could be removed:\n\n")
            for file in sorted(unused_files):
                f.write(f"- `{file}`\n")
        
        f.write("\n## Recommendations\n\n")
        f.write("1. **Review unused files** - Verify they're not needed before deleting\n")
        f.write("2. **Check for dead code** - Some might be imported but functions unused\n")
        f.write("3. **Consider archiving** - Move to `archive/` instead of deleting\n")
        f.write("4. **Update documentation** - Ensure README reflects actual codebase\n")
    
    print(f"\n✅ Detailed report saved to: CALL_GRAPH_ANALYSIS.md")

if __name__ == "__main__":
    main()
