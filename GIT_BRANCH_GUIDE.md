# Git Branch Name Specification Guide

## 🌿 **Important: Source Branch vs Migration Branch**

There are **two different branch concepts** in this Spring migration tool:

### **📥 Source Branch** (`--source-branch`)
- **What it is**: The branch you want to **fetch and analyze** from the GitHub repository
- **When to use**: When the code you want to migrate is not on the default branch
- **Example**: `--source-branch develop` to analyze the develop branch of the repository

### **📤 Migration Branch** (`--git-branch`)  
- **What it is**: The branch that will be **created in your migration workspace** for the changes
- **When to use**: When you want to organize your migration work in a specific branch
- **Example**: `--git-branch feature/spring-6-upgrade` to create a feature branch for your changes

### **🔄 Complete Example**
```bash
# Analyze the 'develop' branch from GitHub and create migration changes in a 'feature/spring-6' branch
python main.py \
  --repo https://github.com/company/spring-app \
  --source-branch develop \
  --git-integration \
  --git-branch feature/spring-6-migration
```

---

## 🌿 **Multiple Ways to Specify Git Branch Names**

You can specify custom git branch names for your Spring migration in several ways:

---

## **1. 📋 Main Migration Tool (Analysis + Git Integration)**

### **With Custom Branch Name:**
```bash
# Analyze and create specific branch
python main.py --dir ./my-spring-project --git-integration --git-branch "feature/spring-6-upgrade"

# Alternative branch naming styles
python main.py --dir ./my-spring-project --git-integration --git-branch "migration/spring-boot-3.x"
python main.py --dir ./my-spring-project --git-integration --git-branch "upgrade/spring-6-jakarta"
python main.py --dir ./my-spring-project --git-integration --git-branch "refactor/javax-to-jakarta"
```

### **With Auto-Generated Branch Name:**
```bash
# Creates branch like: spring-6-migration-20241225_143022
python main.py --dir ./my-spring-project --git-integration
```

---

## **2. 🔧 Migration Git Helper (Post-Analysis)**

### **Command Line Branch Creation:**
```bash
# Create specific branch in existing workspace
python migration_git_helper.py --branch "feature/spring-6-migration"

# Create branch with auto-generated name
python migration_git_helper.py --branch ""

# Other operations with branch context
python migration_git_helper.py --workspace ./my_project_migration_20241225 --branch "hotfix/spring-migration"
```

### **Interactive Branch Creation:**
```bash
python migration_git_helper.py
# Choose "9. [branch] Create migration branch"
# Enter custom name or press Enter for auto-generated
```

---

## **3. 📱 Interactive Workflow**

When you run the migration tool with the interactive prompt:

```bash
python main.py --dir ./my-spring-project
# When prompted to apply changes, the tool will ask:
# "🌿 Git branch name (or Enter for auto-generated): "
```

You can specify:
- **Custom names**: `feature/spring-6-upgrade`
- **Empty for auto**: Just press Enter
- **Pattern examples**: `migration/spring-boot-3`, `upgrade/jakarta-ee-10`

---

## **4. 🎯 Examples of Good Branch Names**

### **Feature-Based Naming:**
```bash
--git-branch "feature/spring-6-migration"
--git-branch "feature/jakarta-ee-migration"
--git-branch "feature/spring-boot-3-upgrade"
```

### **Version-Based Naming:**
```bash
--git-branch "upgrade/spring-6.1"
--git-branch "migrate/spring-boot-2.7-to-3.2"
--git-branch "version/spring-6-compatibility"
```

### **Task-Based Naming:**
```bash
--git-branch "refactor/javax-to-jakarta"
--git-branch "migration/spring-security-6"
--git-branch "update/spring-dependencies"
```

### **Team Convention Examples:**
```bash
--git-branch "PROJ-123/spring-migration"     # Jira ticket
--git-branch "dev/alice/spring-6-upgrade"    # Developer prefix
--git-branch "sprint-45/spring-migration"    # Sprint-based
```

---

## **5. 🔄 Complete Workflow Examples**

### **Scenario A: Start from Scratch with Custom Branch**
```bash
# 1. Run analysis with specific branch
python main.py --dir ./my-spring-project --git-integration --git-branch "feature/spring-6-migration"

# 2. Review and apply changes interactively
# Tool will create workspace with your specified branch

# 3. Make additional changes if needed
cd migration_analysis/my_project_migration_20241225/
git status
git diff
```

### **Scenario B: Analysis First, Branch Later**
```bash
# 1. Run analysis only
python main.py --dir ./my-spring-project

# 2. Create branch with specific name
python migration_git_helper.py --branch "feature/spring-6-migration"

# 3. Work with the branch
python migration_git_helper.py --status
```

### **Scenario C: Interactive Full Workflow**
```bash
# 1. Start interactive analysis
python main.py --dir ./my-spring-project

# 2. When prompted for branch name, specify:
"feature/spring-6-upgrade"

# 3. Use git helper for ongoing management
python migration_git_helper.py
```

---

## **6. 🛡️ Branch Name Validation**

The tools automatically handle:

### **Valid Characters:**
- Letters, numbers, hyphens, underscores, forward slashes
- Examples: `feature/spring-6`, `migration_v1`, `spring-2024`

### **Invalid Characters (Auto-Cleaned):**
- Spaces → replaced with hyphens
- Special chars → removed or replaced
- Example: `"Spring 6 Migration!"` → `"spring-6-migration"`

### **Length Limits:**
- Max 250 characters (git limit)
- Minimum 3 characters
- Auto-generates fallback if invalid

---

## **7. 🔗 Integration with Git Workflows**

### **GitFlow Compatible:**
```bash
--git-branch "feature/spring-6-migration"      # Feature branch
--git-branch "hotfix/spring-security-fix"      # Hotfix branch  
--git-branch "release/spring-6-compatibility"  # Release branch
```

### **GitHub Flow Compatible:**
```bash
--git-branch "spring-6-migration"              # Simple feature
--git-branch "upgrade-spring-dependencies"     # Descriptive name
```

### **Custom Team Workflows:**
```bash
--git-branch "dev/spring-migration"            # Development prefix
--git-branch "TICKET-123/spring-upgrade"       # Ticket-based
--git-branch "v3.0.0/spring-6-migration"       # Version-based
```

---

## **8. 📊 Auto-Generated Branch Formats**

When you don't specify a branch name, the tools create:

### **Main Tool Format:**
```
spring-6-migration-YYYYMMDD_HHMMSS
Example: spring-6-migration-20241225_143022
```

### **Git Helper Format:**
```
spring-6-migration-YYYYMMDD_HHMMSS
Example: spring-6-migration-20241225_143045
```

### **Format Benefits:**
- ✅ Unique timestamps prevent conflicts
- ✅ Clear purpose indication
- ✅ Sortable by creation time
- ✅ Safe for all git hosting platforms

---

## **9. 💡 Best Practices**

### **Naming Conventions:**
1. **Be Descriptive**: `spring-6-migration` vs `fix`
2. **Use Consistent Format**: Team-wide conventions
3. **Include Context**: `PROJ-123/spring-upgrade`
4. **Avoid Conflicts**: Check existing branch names

### **Workflow Integration:**
1. **Plan Branch Strategy**: Before starting migration
2. **Coordinate with Team**: Avoid parallel migrations
3. **Use Pull Requests**: For code review and testing
4. **Document Changes**: In commit messages and PR descriptions

### **Branch Lifecycle:**
1. **Create**: With descriptive name
2. **Work**: Make incremental commits
3. **Test**: Validate migration changes
4. **Review**: Team code review process
5. **Merge**: Into main/develop branch
6. **Cleanup**: Delete after successful merge

---

## **10. 🚀 Quick Reference**

### **Most Common Commands:**
```bash
# Custom branch with main tool
python main.py --dir ./project --git-integration --git-branch "feature/spring-6"

# Custom branch with git helper
python migration_git_helper.py --branch "feature/spring-6"

# Interactive branch creation
python migration_git_helper.py
# Choose option "9"
```

### **Branch Name Ideas:**
- `feature/spring-6-migration`
- `upgrade/spring-boot-3.x`
- `migration/jakarta-ee-10`
- `refactor/javax-to-jakarta`
- `version/spring-6.1.0`

This gives you complete control over your git branch naming for Spring migrations! 🎯 