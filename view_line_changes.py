#!/usr/bin/env python3
"""
View Line Changes Utility

Shows detailed line-by-line changes from Spring migration analysis results.
Helps you see exactly which lines were modified in each file.
"""

import os
import sys
import json
import argparse
from pathlib import Path


class LineChangeViewer:
    def __init__(self, migration_analysis_dir=None):
        """Initialize the line change viewer."""
        if migration_analysis_dir:
            self.analysis_dir = Path(migration_analysis_dir)
        else:
            self.analysis_dir = self._find_latest_analysis_dir()
        
        if not self.analysis_dir or not self.analysis_dir.exists():
            raise ValueError("Migration analysis directory not found")
        
        print(f"📂 Using analysis directory: {self.analysis_dir}")
    
    def _find_latest_analysis_dir(self):
        """Find the latest migration analysis directory."""
        current_dir = Path.cwd()
        analysis_dir = current_dir / "migration_analysis"
        
        if analysis_dir.exists():
            return analysis_dir
        
        # Look for analysis directories in current directory
        analysis_dirs = [d for d in current_dir.iterdir() 
                        if d.is_dir() and "migration" in d.name.lower()]
        
        if analysis_dirs:
            # Return the most recent one
            analysis_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return analysis_dirs[0]
        
        return None
    
    def load_line_change_report(self):
        """Load the line change report from migration results."""
        # Look for migration report files
        report_files = list(self.analysis_dir.glob("*_spring_migration_report.json"))
        
        if not report_files:
            raise FileNotFoundError("No migration report found. Run the migration analysis first.")
        
        # Use the most recent report
        report_file = max(report_files, key=lambda x: x.stat().st_mtime)
        print(f"📄 Loading report: {report_file.name}")
        
        with open(report_file, 'r', encoding='utf-8') as f:
            full_report = json.load(f)
        
        # Try to extract line change report from shared state
        line_report = full_report.get("line_change_report")
        if not line_report:
            # Fallback: try to reconstruct from generated_changes
            generated_changes = full_report.get("generated_changes", {})
            if generated_changes:
                print("📝 Reconstructing line change report from generated changes...")
                line_report = self._reconstruct_line_report(generated_changes)
            else:
                raise ValueError("No line change data found in migration report")
        
        return line_report
    
    def _reconstruct_line_report(self, generated_changes):
        """Reconstruct line change report from generated changes."""
        line_report = {
            "files_modified": {},
            "summary": {
                "total_files": 0,
                "total_lines_changed": 0,
                "changes_by_type": {}
            }
        }
        
        all_files = set()
        total_lines = 0
        changes_by_type = {}
        
        for category, change_list in generated_changes.items():
            if not isinstance(change_list, list):
                continue
            
            for change in change_list:
                if not isinstance(change, dict):
                    continue
                
                file_path = change.get("file", "unknown")
                change_type = change.get("type", "unknown")
                line_numbers = change.get("line_numbers", [])
                description = change.get("description", "")
                
                if file_path not in line_report["files_modified"]:
                    line_report["files_modified"][file_path] = {
                        "changes": [],
                        "line_count": 0,
                        "categories": []
                    }
                
                line_report["files_modified"][file_path]["changes"].append({
                    "type": change_type,
                    "category": category,
                    "description": description,
                    "line_numbers": line_numbers,
                    "automatic": change.get("automatic", False)
                })
                
                if category not in line_report["files_modified"][file_path]["categories"]:
                    line_report["files_modified"][file_path]["categories"].append(category)
                
                all_files.add(file_path)
                total_lines += len(line_numbers) if line_numbers else 1
                changes_by_type[change_type] = changes_by_type.get(change_type, 0) + 1
        
        # Update line counts
        for file_path in line_report["files_modified"]:
            changes = line_report["files_modified"][file_path]["changes"]
            all_lines = set()
            for change in changes:
                all_lines.update(change.get("line_numbers", []))
            line_report["files_modified"][file_path]["line_count"] = len(all_lines)
        
        line_report["summary"] = {
            "total_files": len(all_files),
            "total_lines_changed": total_lines,
            "changes_by_type": changes_by_type
        }
        
        return line_report
    
    def show_summary(self, line_report):
        """Show a summary of all line changes."""
        summary = line_report.get("summary", {})
        files_modified = line_report.get("files_modified", {})
        
        print(f"\n🔍 Migration Line Changes Summary")
        print("=" * 50)
        print(f"📁 Total Files Modified: {summary.get('total_files', 0)}")
        print(f"📝 Total Lines Changed: {summary.get('total_lines_changed', 0)}")
        
        changes_by_type = summary.get("changes_by_type", {})
        if changes_by_type:
            print(f"\n🏷️  Change Types:")
            for change_type, count in sorted(changes_by_type.items()):
                print(f"   {change_type}: {count}")
        
        print(f"\n📄 Files Overview:")
        for file_path, file_info in sorted(files_modified.items()):
            changes = file_info.get("changes", [])
            line_count = file_info.get("line_count", 0)
            categories = file_info.get("categories", [])
            
            auto_count = sum(1 for c in changes if c.get("automatic", False))
            manual_count = len(changes) - auto_count
            
            print(f"   📄 {file_path}")
            print(f"      📝 {len(changes)} changes (~{line_count} lines)")
            print(f"      🤖 {auto_count} automatic, 👤 {manual_count} manual")
            print(f"      🏷️  {', '.join(categories)}")
    
    def show_detailed_changes(self, line_report, file_filter=None):
        """Show detailed line-by-line changes."""
        files_modified = line_report.get("files_modified", {})
        
        print(f"\n📋 Detailed Line-by-Line Changes")
        print("=" * 50)
        
        for file_path, file_info in sorted(files_modified.items()):
            # Apply file filter if specified
            if file_filter and file_filter.lower() not in file_path.lower():
                continue
            
            changes = file_info.get("changes", [])
            line_count = file_info.get("line_count", 0)
            categories = file_info.get("categories", [])
            
            print(f"\n📄 {file_path}")
            print(f"   📊 {len(changes)} changes affecting ~{line_count} lines")
            print(f"   🏷️  Categories: {', '.join(categories)}")
            print()
            
            for i, change in enumerate(changes, 1):
                line_numbers = change.get("line_numbers", [])
                change_type = change.get("type", "unknown")
                description = change.get("description", "")
                automatic = change.get("automatic", False)
                category = change.get("category", "")
                
                auto_marker = "🤖 AUTO" if automatic else "👤 MANUAL"
                line_range = self._format_line_range(line_numbers)
                
                print(f"   {i:2d}. {auto_marker} | {change_type}")
                print(f"       📝 {description}")
                print(f"       📍 Lines: {line_range}")
                print(f"       🏷️  Category: {category}")
                print()
    
    def show_file_changes(self, line_report, file_path):
        """Show changes for a specific file."""
        files_modified = line_report.get("files_modified", {})
        
        if file_path not in files_modified:
            print(f"❌ No changes found for file: {file_path}")
            print(f"\n📄 Available files:")
            for f in sorted(files_modified.keys()):
                print(f"   {f}")
            return
        
        file_info = files_modified[file_path]
        changes = file_info.get("changes", [])
        line_count = file_info.get("line_count", 0)
        categories = file_info.get("categories", [])
        
        print(f"\n📄 Changes in {file_path}")
        print("=" * 60)
        print(f"📊 {len(changes)} changes affecting ~{line_count} lines")
        print(f"🏷️  Categories: {', '.join(categories)}")
        print()
        
        for i, change in enumerate(changes, 1):
            line_numbers = change.get("line_numbers", [])
            change_type = change.get("type", "unknown")
            description = change.get("description", "")
            automatic = change.get("automatic", False)
            category = change.get("category", "")
            
            auto_marker = "🤖 AUTOMATIC" if automatic else "👤 MANUAL REVIEW"
            line_range = self._format_line_range(line_numbers)
            
            print(f"{i:2d}. [{auto_marker}] {change_type}")
            print(f"    📝 {description}")
            print(f"    📍 Lines: {line_range}")
            print(f"    🏷️  Category: {category}")
            
            # Show additional details if available
            from_value = change.get("from", "")
            to_value = change.get("to", "")
            if from_value and to_value:
                print(f"    🔄 Change: {from_value} → {to_value}")
            
            explanation = change.get("explanation", "")
            if explanation:
                print(f"    💡 {explanation}")
            
            print()
    
    def _format_line_range(self, line_numbers):
        """Format line numbers into a readable range string."""
        if not line_numbers:
            return "Location TBD"
        
        if len(line_numbers) == 1:
            return f"Line {line_numbers[0]}"
        
        sorted_lines = sorted(set(line_numbers))
        if len(sorted_lines) <= 5:
            return f"Lines {', '.join(map(str, sorted_lines))}"
        
        return f"Lines {min(sorted_lines)}-{max(sorted_lines)} ({len(sorted_lines)} total)"
    
    def export_to_file(self, line_report, output_file):
        """Export line change report to a file."""
        output_path = Path(output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Spring Migration Line Changes Report\n\n")
            
            summary = line_report.get("summary", {})
            f.write(f"## Summary\n")
            f.write(f"- **Files Modified**: {summary.get('total_files', 0)}\n")
            f.write(f"- **Lines Changed**: {summary.get('total_lines_changed', 0)}\n\n")
            
            changes_by_type = summary.get("changes_by_type", {})
            if changes_by_type:
                f.write(f"### Change Types\n")
                for change_type, count in sorted(changes_by_type.items()):
                    f.write(f"- {change_type}: {count}\n")
                f.write("\n")
            
            files_modified = line_report.get("files_modified", {})
            f.write(f"## Detailed Changes\n\n")
            
            for file_path, file_info in sorted(files_modified.items()):
                changes = file_info.get("changes", [])
                line_count = file_info.get("line_count", 0)
                categories = file_info.get("categories", [])
                
                f.write(f"### {file_path}\n")
                f.write(f"- **Changes**: {len(changes)}\n")
                f.write(f"- **Lines Affected**: ~{line_count}\n")
                f.write(f"- **Categories**: {', '.join(categories)}\n\n")
                
                for i, change in enumerate(changes, 1):
                    line_numbers = change.get("line_numbers", [])
                    change_type = change.get("type", "unknown")
                    description = change.get("description", "")
                    automatic = change.get("automatic", False)
                    
                    auto_status = "Automatic" if automatic else "Manual Review"
                    line_range = self._format_line_range(line_numbers)
                    
                    f.write(f"{i}. **{change_type}** ({auto_status})\n")
                    f.write(f"   - Description: {description}\n")
                    f.write(f"   - Location: {line_range}\n")
                    
                    from_value = change.get("from", "")
                    to_value = change.get("to", "")
                    if from_value and to_value:
                        f.write(f"   - Change: `{from_value}` → `{to_value}`\n")
                    
                    f.write("\n")
                
                f.write("\n")
        
        print(f"✅ Line change report exported to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="View detailed line-by-line changes from Spring migration analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show summary of all changes
  python view_line_changes.py --summary

  # Show detailed changes for all files
  python view_line_changes.py --detailed

  # Show changes for specific file
  python view_line_changes.py --file src/main/java/User.java

  # Filter files by name pattern
  python view_line_changes.py --detailed --filter "Controller"

  # Export report to markdown file
  python view_line_changes.py --export line_changes.md

  # Use specific analysis directory
  python view_line_changes.py --dir ./custom_analysis --summary
        """
    )
    
    parser.add_argument(
        "--dir", 
        help="Migration analysis directory path"
    )
    parser.add_argument(
        "--summary", "-s",
        action="store_true",
        help="Show summary of line changes"
    )
    parser.add_argument(
        "--detailed", "-d",
        action="store_true", 
        help="Show detailed line-by-line changes"
    )
    parser.add_argument(
        "--file", "-f",
        help="Show changes for specific file"
    )
    parser.add_argument(
        "--filter",
        help="Filter files by name pattern (works with --detailed)"
    )
    parser.add_argument(
        "--export", "-e",
        help="Export line change report to file"
    )
    
    args = parser.parse_args()
    
    try:
        viewer = LineChangeViewer(args.dir)
        line_report = viewer.load_line_change_report()
        
        if args.summary or (not args.detailed and not args.file and not args.export):
            viewer.show_summary(line_report)
        
        if args.detailed:
            viewer.show_detailed_changes(line_report, args.filter)
        
        if args.file:
            viewer.show_file_changes(line_report, args.file)
        
        if args.export:
            viewer.export_to_file(line_report, args.export)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 