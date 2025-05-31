# Git Integration Guide for Spring Migration Tool

## 🚀 Overview

The Spring Migration Tool now includes comprehensive Git integration that seamlessly handles version control operations during the migration process. This guide covers how to compare changes, commit modifications, and push updates to repositories.

## 📋 Table of Contents

1. [Git Integration Features](#git-integration-features)
2. [Usage Examples](#usage-examples)
3. [Workflow Details](#workflow-details)
4. [Safety Features](#safety-features)
5. [Command Reference](#command-reference)
6. [Troubleshooting](#troubleshooting)

## 🔧 Git Integration Features

### Automatic Workflow
- **🔍 Change Analysis**: Detailed diff summary of all modifications
- **🌿 Branch Management**: Automatic creation of timestamped migration branches
- **📋 Staging**: Smart staging of migration-related changes
- **💾 Committing**: Descriptive commits with migration metadata
- **🚀 Remote Push**: Optional push to remote repositories
- **📝 PR Templates**: Auto-generated pull request descriptions

### Interactive Control
- **👥 User Confirmation**: Interactive approval for each Git operation
- **📊 Diff Preview**: Detailed change summary before committing
- **🎯 Selective Operations**: Choose which Git operations to perform

## 🎯 Usage Examples

### Complete Migration with Git Integration

```bash
# Full migration workflow with Git management
python main.py --mode spring-migration \
    --dir /path/to/spring/project \
    --apply-changes \
    --git-integration \
    --output-dir ./migration-results
```

### Analysis Only (No Git Operations)

```bash
# Analyze remote repository without Git operations
python main.py --mode spring-migration \
    --repo https://github.com/user/spring-app \
    --token your_github_token \
    --output-dir ./analysis-results
```

### Local Analysis with Manual Git Control

```bash
# Apply changes but manage Git manually
python main.py --mode spring-migration \
    --dir /path/to/local/project \
    --apply-changes \
    --output-dir ./results

# Then manually manage Git:
git add .
git commit -m "Spring 5 to 6 migration changes"
git push
```

## 🔄 Workflow Details

### Phase 1: Pre-Migration Analysis
```
🔍 Repository Analysis
├── Check Git repository status
├── Identify current branch
├── Verify remote configuration
└── Analyze file structure
```

### Phase 2: Migration Execution
```
🔧 Migration Process
├── 📦 Create timestamped backup
├── 🤖 LLM-powered change detection
├── ✅ User confirmation of changes
├── ⚡ Apply approved modifications
└── 📊 Generate change summary
```

### Phase 3: Git Operations
```
🔀 Git Integration Workflow
├── 🌿 Create migration branch: spring-migration-YYYYMMDD_HHMMSS
├── 📋 Stage all migration changes
├── 📈 Show detailed diff summary
├── 💾 Interactive commit decision
├── 🚀 Optional remote push
└── 📝 Generate PR template
```

## 🛡️ Safety Features

### 📦 Backup System
- **Automatic Backup**: Complete file backup before any changes
- **Timestamp Organization**: Backups organized by timestamp
- **Manifest File**: JSON manifest with file mapping for restoration
- **Easy Recovery**: Simple restoration process if issues occur

### 🌿 Branch Isolation
- **Dedicated Branches**: All changes isolated on migration-specific branches
- **No Main Branch Changes**: Original branch remains untouched
- **Clean Rollback**: Easy return to original state

### 👥 Interactive Control
- **Confirmation Steps**: User approval required for each Git operation
- **Preview Mode**: Detailed preview of changes before application
- **Granular Control**: Choose commit/push operations independently

### 📋 Audit Trail
- **Detailed Commit Messages**: Comprehensive descriptions of changes
- **Change Metadata**: Statistics on applied and skipped changes
- **Migration Context**: Project details and timestamp information

## 💻 Command Reference

### Core Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--mode spring-migration` | Enable Spring migration mode | Required |
| `--dir /path/to/project` | Local repository path | For local projects |
| `--repo https://github.com/user/repo` | Remote repository URL | For GitHub analysis |
| `--apply-changes` | Apply migration changes | Required for modifications |
| `--git-integration` | Enable Git operations | Optional but recommended |
| `--output-dir ./results` | Output directory | Optional, defaults to ./output |

### Git-Specific Options

| Scenario | Command |
|----------|---------|
| **Full Migration** | `--apply-changes --git-integration` |
| **Analysis Only** | *(no additional flags)* |
| **Manual Git** | `--apply-changes` *(without --git-integration)* |

## 📊 Example Git Operations Output

```
🔀 GIT OPERATIONS SUMMARY
============================================================
📊 Changes Summary:
   📝 Modified files: 12
   ➕ Added files: 0
   ➖ Deleted files: 0
   ❓ Untracked files: 0

📈 Diff Summary:
   Files changed: 12
   Lines added: +24
   Lines deleted: -24

🌿 Branch: spring-migration-20241215_143022
🏠 Repository: git@github.com:user/spring-app.git
============================================================
💾 Commit these migration changes? [y/N]: y
🚀 Push to remote repository? [y/N]: y

✅ Created commit: a1b2c3d4
✅ Pushed branch 'spring-migration-20241215_143022' to remote

📝 Ready for Pull Request:
   Title: Spring 5 to 6 Migration - Automated Changes for MyApp
   Branch: spring-migration-20241215_143022
   
💡 Create a pull request on your Git platform with the generated title and description.
```

## 📝 Generated Commit Message Example

```
Spring 5 to 6 Migration - Automated Changes

- Applied 8 automatic migration changes
- 4 changes marked for manual review
- Jakarta namespace migration (javax.* → jakarta.*)
- Updated import statements and references

Generated by AI Codebase Migration Tool
Project: MySpringApp
Date: 2024-12-15 14:30:22
```

## 📋 Pull Request Template

The tool automatically generates a comprehensive PR description:

```markdown
## Spring Framework Migration

This pull request contains automated migration changes from Spring 5 to Spring 6.

### Changes Applied
- ✅ **8 automatic changes** applied successfully
- ⚠️ **4 changes** require manual review

### Migration Details
- **Jakarta Namespace**: Updated `javax.*` imports to `jakarta.*`
- **Import Updates**: Cleaned up package references
- **Configuration**: Basic property updates where applicable

### Manual Review Required
- `SecurityConfig.java`: Spring Security WebSecurityConfigurerAdapter migration (manual review required)
- `pom.xml`: Dependency version updates (manual review required)
- `DataSourceConfig.java`: Configuration pattern updates (manual review required)
- `UserController.java`: Complex validation logic (manual review required)

### Testing
- [ ] Application builds successfully
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

### Generated by
🤖 AI Codebase Migration Tool
```

## 🚨 Troubleshooting

### Common Issues

#### Git Repository Not Found
```bash
⚠️ Directory is not a Git repository: /path/to/project
```
**Solution**: Initialize Git repository first:
```bash
cd /path/to/project
git init
git add .
git commit -m "Initial commit"
```

#### Remote Repository Not Configured
```bash
📍 Local repository only (no remote configured)
```
**Solution**: Add remote repository:
```bash
git remote add origin https://github.com/user/repo.git
```

#### No Changes to Commit
```bash
No changes detected
```
**Solution**: This is normal if no migration changes were required or all changes were skipped.

### Rollback Procedures

#### If Using Git Integration
```bash
# Return to original branch
git checkout main

# Delete migration branch (optional)
git branch -D spring-migration-20241215_143022

# If pushed to remote, delete remote branch
git push origin --delete spring-migration-20241215_143022
```

#### If Backup Restoration Needed
```bash
# Locate backup directory (shown in tool output)
# Example: MyProject_backup_20241215_143022/

# Restore specific files manually or entire directory
cp -r MyProject_backup_20241215_143022/* /path/to/project/
```

## 🎯 Best Practices

### Before Migration
1. **Ensure Clean Working Directory**: Commit or stash any pending changes
2. **Backup Important Data**: Additional backup beyond tool's automatic backup
3. **Review Branch Strategy**: Understand your team's branching workflow
4. **Check Remote Access**: Ensure you have push permissions if using `--git-integration`

### During Migration
1. **Review Changes Carefully**: Use preview mode to understand modifications
2. **Test Incrementally**: Consider smaller migrations for large projects
3. **Document Decisions**: Note why certain changes were skipped for manual review
4. **Coordinate with Team**: Communicate migration plans with team members

### After Migration
1. **Create Pull Request**: Use generated template for consistent documentation
2. **Comprehensive Testing**: Build, test, and validate application functionality
3. **Manual Review Completion**: Address all items flagged for manual review
4. **Merge Strategy**: Follow team's merge/rebase practices

## 🔗 Integration with CI/CD

The Git integration is designed to work seamlessly with CI/CD pipelines:

### GitHub Actions Example
```yaml
name: Spring Migration Review
on:
  pull_request:
    branches: [ main ]
    
jobs:
  migration-review:
    if: contains(github.head_ref, 'spring-migration')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Java
        uses: actions/setup-java@v2
        with:
          java-version: '17'
      - name: Build Project
        run: ./mvnw clean compile
      - name: Run Tests
        run: ./mvnw test
```

### Benefits
- **Automated Testing**: CI/CD automatically tests migration changes
- **Consistent Process**: Standardized migration workflow across team
- **Quality Gates**: Automated checks before merge approval
- **Documentation**: Integration with issue tracking and documentation systems

---

## 📚 Additional Resources

- [Spring Boot 3 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide)
- [Jakarta EE Migration Guide](https://jakarta.ee/resources/guides/jakarta-ee-migration-guide/)
- [Git Best Practices](https://git-scm.com/book/en/v2)

---

*Generated by AI Codebase Migration Tool - Git Integration Guide* 