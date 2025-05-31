# Spring 5 to 6 Migration Tool

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
 <a href="https://discord.gg/hUHHE9Sa6T">
    <img src="https://img.shields.io/discord/1346833819172601907?logo=discord&style=flat">
</a>

> *Comprehensive AI-powered tool for analyzing and migrating Spring Framework projects from Spring 5 to Spring 6 with Jakarta EE compatibility.*

<p align="center">
  <img
    src="./assets/banner.png" width="800"
  />
</p>

This tool uses advanced LLM analysis to understand your Spring codebase and provides intelligent migration assistance from Spring Framework 5.x to Spring Framework 6.x, including Jakarta EE namespace migration and Spring Security updates.

## 🚀 Key Features

- **🤖 LLM-Powered Analysis**: Uses advanced language models to understand code context and generate precise migration changes
- **📍 Line-by-Line Detection**: Identifies exact locations where changes are needed with specific line numbers
- **🧠 Context-Aware Changes**: Goes beyond simple pattern matching to understand the semantic meaning of code
- **💡 Detailed Explanations**: Provides clear explanations for why each change is necessary
- **🎯 Smart Safety Classification**: Automatically categorizes changes as safe (automatic) or requiring manual review
- **📦 Automatic Change Application**: Safely applies migration changes like javax.* to jakarta.* replacements
- **🔒 Interactive Confirmation**: Shows users exactly what changes will be made before applying them
- **📋 Backup Creation**: Automatically creates backups before making any changes
- **🔀 Git Integration**: Seamless Git workflow with branching, committing, and push operations
- **📊 Structured Output**: JSON and markdown reports suitable for integration with other tools

## 📋 What Gets Migrated

### ✅ Automatic Changes (Safe)
- `javax.*` to `jakarta.*` namespace migration
- Import statement updates
- Package reference corrections
- Basic configuration property updates

### ⚠️ Manual Review Required
- Spring Security `WebSecurityConfigurerAdapter` → `SecurityFilterChain`
- Spring Boot 2.x → 3.x dependency updates
- Complex configuration pattern migrations
- Custom authentication/authorization logic

## 🛠️ Installation

1. Clone this repository
   ```bash
   git clone https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge
   cd PocketFlow-Tutorial-Codebase-Knowledge
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up LLM in [`utils/call_llm.py`](./utils/call_llm.py) by providing credentials. By default, you can use the [AI Studio key](https://aistudio.google.com/app/apikey) with this client for Gemini Pro 2.5:

   ```python
   client = genai.Client(
     api_key=os.getenv("GEMINI_API_KEY", "your-api_key"),
   )
   ```

   You can verify that it is correctly set up by running:
   ```bash
   python utils/call_llm.py
   ```

4. **For Private Repositories**: Set up your GitHub Personal Access Token
   
   **Option 1: Environment Variable (Recommended)**
   ```bash
   export GITHUB_TOKEN="your_github_personal_access_token_here"
   ```
   
   **Option 2: Command Line Argument**
   ```bash
   python main.py --repo https://github.com/username/private-repo --token "your_github_token"
   ```

## 📖 Usage

### Analysis Only (Read-Only)

```bash
# Analyze a GitHub repository (no changes made)
python main.py --repo https://github.com/username/spring-project

# Analyze a private repository with token
python main.py --repo https://github.com/username/private-spring-project --token "your_github_token"

# Analyze with environment variable
export GITHUB_TOKEN="your_token"
python main.py --repo https://github.com/username/private-spring-project
```

### Migration with Change Application

```bash
# Analyze local project and apply safe changes interactively
python main.py --dir /path/to/spring/project --apply-changes

# With Git integration for seamless workflow
python main.py --dir /path/to/spring/project --apply-changes --git-integration

# Specify custom output directory
python main.py --dir /path/to/spring/project --apply-changes -o ./migration-results
```

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--repo` | GitHub repository URL | `--repo https://github.com/user/spring-app` |
| `--dir` | Local directory path | `--dir /path/to/project` |
| `--apply-changes` | Apply migration changes | Required for modifications |
| `--git-integration` | Enable Git operations | Recommended with `--apply-changes` |
| `-t, --token` | GitHub token | `--token your_github_token` |
| `-o, --output` | Output directory | `--output ./results` |
| `--no-cache` | Disable LLM caching | For fresh analysis |
| `-i, --include` | Include file patterns | `--include "*.java" "*.xml"` |
| `-e, --exclude` | Exclude file patterns | `--exclude "test/*" "target/*"` |

## 🔀 Git Integration

The tool includes comprehensive Git integration for managing migration changes:

### Automatic Git Workflow

When using `--git-integration` with `--apply-changes`:

1. **📊 Analyze Changes**: Show detailed diff summary
2. **🌿 Create Branch**: Timestamped migration branch  
3. **📋 Stage Changes**: Stage migration-related files
4. **💾 Commit**: Create descriptive commit
5. **🚀 Push**: Optional push to remote
6. **📝 PR Ready**: Generate pull request template

### Example Git Workflow

```bash
# Full migration with Git integration
python main.py --dir /path/to/spring/project --apply-changes --git-integration
```

**Interactive Output:**
```
🔀 GIT OPERATIONS SUMMARY
============================================================
📊 Changes Summary:
   📝 Modified files: 12
   Lines added: +24, deleted: -24

🌿 Branch: spring-migration-20241215_143022
💾 Commit these migration changes? [y/N]: y
🚀 Push to remote repository? [y/N]: y

✅ Created commit: a1b2c3d4
✅ Ready for Pull Request
```

## 📊 Output Structure

```
migration-results/
├── MyProject_spring_migration_report.json    # Detailed analysis
├── MyProject_migration_summary.md            # Human-readable summary  
├── MyProject_backup_20241215_143022/         # File backup
│   ├── backup_manifest.json
│   └── [original files...]
└── README.md                                 # Migration instructions
```

## 🛡️ Safety Features

### Backup System
- **📦 Automatic Backup**: Complete file backup before changes
- **📋 Backup Manifest**: JSON mapping for restoration
- **🔄 Easy Recovery**: Simple restoration process

### Git Safety
- **🌿 Branch Isolation**: Changes on dedicated branch
- **💾 Detailed Commits**: Comprehensive commit messages
- **🚀 Remote Push**: Optional team collaboration
- **📝 PR Templates**: Auto-generated descriptions

### Interactive Control
- **👥 User Confirmation**: Approval required for operations
- **📊 Change Preview**: Detailed preview before application
- **⚡ Granular Control**: Choose specific operations

## 🔄 Rollback Process

### Git Rollback
```bash
# Return to original branch
git checkout main

# Delete migration branch
git branch -D spring-migration-20241215_143022

# Delete remote branch (if pushed)
git push origin --delete spring-migration-20241215_143022
```

### File Restoration
```bash
# Restore from backup directory
cp -r MyProject_backup_20241215_143022/* /path/to/project/
```

## 🎯 Migration Categories

### Framework Updates
- Spring Boot 2.x → 3.x version updates
- Spring Framework 5.x → 6.x migration
- Dependency compatibility checks

### Jakarta EE Migration
- `javax.persistence` → `jakarta.persistence`
- `javax.servlet` → `jakarta.servlet`
- `javax.validation` → `jakarta.validation`
- Import statement corrections

### Spring Security
- `WebSecurityConfigurerAdapter` removal
- `SecurityFilterChain` implementation
- Configuration DSL updates
- Authentication/authorization modernization

### Testing & Build
- JUnit 4 → 5 migration suggestions
- Maven/Gradle plugin updates
- Test framework compatibility
- CI/CD configuration updates

## 💻 Example Migration Changes

### Jakarta Namespace
```java
// Before
import javax.persistence.Entity;
import javax.persistence.Table;

// After
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
```

### Spring Security
```java
// Before
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    // Legacy configuration
}

// After
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        // Modern configuration
    }
}
```

## 🚨 Troubleshooting

### Common Issues

**Git Repository Not Found**
```bash
cd /path/to/project
git init
git add .
git commit -m "Initial commit"
```

**No GitHub Token**
```bash
export GITHUB_TOKEN="your_personal_access_token"
```

**Large Project Analysis**
```bash
# Increase file size limit for large files
python main.py --dir /path/to/project --max-size 200000
```

## 📚 Migration Resources

- [Spring Boot 3 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide)
- [Jakarta EE Migration Guide](https://jakarta.ee/resources/guides/jakarta-ee-migration-guide/)
- [Spring Security 6 Migration](https://spring.io/blog/2022/02/21/spring-security-without-the-websecurityconfigureradapter)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Built with [Pocket Flow](https://github.com/The-Pocket/PocketFlow) - A 100-line LLM framework for building AI agents*



