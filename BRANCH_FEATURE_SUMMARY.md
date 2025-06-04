# Source Branch Support - Feature Summary

## 🌿 **New Feature: `--source-branch` Support**

You can now specify which branch to fetch and analyze from GitHub repositories using the `--source-branch` parameter.

---

## 🚀 **Quick Usage**

### **Basic Examples**
```bash
# Analyze the default branch (same as before)
python main.py --repo https://github.com/user/spring-project

# Analyze specific branch
python main.py --repo https://github.com/user/spring-project --source-branch develop

# Analyze feature branch
python main.py --repo https://github.com/user/spring-project --source-branch feature/spring-upgrade

# Analyze release branch  
python main.py --repo https://github.com/user/spring-project --source-branch release/v2.0
```

### **With Other Options**
```bash
# Private repo with token and specific branch
python main.py --repo https://github.com/company/private-repo \
  --source-branch develop \
  --github-token YOUR_TOKEN \
  --apply-changes

# Large repo with optimizations and branch
python main.py --repo https://github.com/user/large-project \
  --source-branch main \
  --parallel \
  --max-files 500 \
  --verbose

# Complete workflow with both source and migration branches
python main.py --repo https://github.com/user/spring-app \
  --source-branch develop \
  --git-integration \
  --git-branch feature/spring-6-migration \
  --apply-changes
```

---

## 🔧 **Technical Implementation**

### **What Changed:**
1. **New CLI Parameter**: `--source-branch BRANCH_NAME`
2. **Enhanced Git Operations**: Automatic branch checkout after cloning
3. **Error Handling**: Clear error messages with available branch suggestions
4. **Verbose Logging**: Shows which branch is being analyzed

### **Branch Resolution:**
- **Local Branch First**: Tries `git checkout branch-name`
- **Remote Branch Fallback**: Tries `git checkout origin/branch-name`  
- **Error with Suggestions**: Lists available branches if branch not found

### **Updated Functions:**
- `crawl_github_files()` - Added `branch` parameter
- `FetchRepo` node - Passes branch info to crawler
- CLI argument parsing - Added `--source-branch`
- Verbose logging - Shows target branch

---

## 💡 **Key Benefits**

### **Development Workflow Support:**
- ✅ Analyze development branches before merging
- ✅ Check feature branches for migration compatibility
- ✅ Validate release branches before deployment
- ✅ Test migration on experimental branches

### **Team Collaboration:**
- ✅ Different team members can analyze different branches
- ✅ Parallel migration work on multiple branches
- ✅ Branch-specific migration strategies
- ✅ Safe experimentation without affecting main

### **CI/CD Integration:**
- ✅ Automated analysis of pull request branches
- ✅ Migration checks as part of branch policies  
- ✅ Release branch validation pipelines
- ✅ Pre-merge migration compatibility checks

---

## 🛡️ **Error Handling**

### **Invalid Branch Names:**
```bash
python main.py --repo https://github.com/user/repo --source-branch invalid-branch
```
**Output:**
```
❌ Failed to checkout branch 'invalid-branch':
   Local checkout error: pathspec 'invalid-branch' did not match any file(s)
   Remote checkout error: pathspec 'origin/invalid-branch' did not match any file(s)
   Available branches: main, develop, feature/new-feature, release/v2.0
```

### **Network Issues:**
- Proper timeout handling during clone operations
- Clear error messages for authentication failures
- Retry logic for temporary network issues

---

## 📊 **Testing Results**

Tested with **Spring Pet Clinic** repository:

| Test Case | Branch | Result | Files Fetched |
|-----------|--------|--------|---------------|
| Default Branch | `(default)` | ✅ SUCCESS | 45 files |
| Explicit Main | `main` | ✅ SUCCESS | 45 files |
| Invalid Branch | `non-existent-branch-12345` | ✅ EXPECTED_ERROR | N/A |

---

## 🔄 **Branch vs Migration Branch**

### **Important Distinction:**

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `--source-branch` | **What to analyze** | `develop`, `feature/upgrade` |
| `--git-branch` | **Where to put changes** | `migration/spring-6` |

### **Complete Example:**
```bash
# Analyze the 'develop' branch and create migration changes in 'feature/spring-6' branch
python main.py \
  --repo https://github.com/company/spring-app \
  --source-branch develop \                    # ← What to analyze
  --git-integration \
  --git-branch feature/spring-6-migration \    # ← Where to put changes
  --apply-changes
```

---

## 📚 **Documentation Updates**

- ✅ Updated `README.md` with examples
- ✅ Added to `GIT_BRANCH_GUIDE.md` 
- ✅ Enhanced CLI help text
- ✅ Created test script (`test_branch_support.py`)

---

## 🎯 **Use Cases**

### **1. Feature Branch Analysis**
```bash
# Before merging a feature branch, check migration impact
python main.py --repo https://github.com/team/app --source-branch feature/new-api
```

### **2. Release Branch Validation**
```bash
# Validate migration readiness of release branch
python main.py --repo https://github.com/team/app --source-branch release/v3.0 --apply-changes
```

### **3. Development Branch Monitoring**
```bash
# Regular analysis of development branch
python main.py --repo https://github.com/team/app --source-branch develop --parallel
```

### **4. Experimental Branch Testing**
```bash
# Test migration on experimental branch without affecting main
python main.py --repo https://github.com/team/app --source-branch experimental/spring-6-preview
```

This feature provides complete flexibility for analyzing any branch of a Spring project for migration readiness! 🎉 