# GitHub Profile Stats Script

A Python script that automatically generates comprehensive GitHub profile statistics including tech stack categorization, user metrics, and programming language rankings using real-time GitHub API data.

## 🚀 Features

### Tech Stack Category Generation
Automatically categorizes and displays your technologies:
- **Primary Technologies**: Rust, Java, Dart with framework detection
- **Additional Technologies**: Frontend development tools (React, Vue.js, SCSS/CSS)
- **Data & Analytics**: Python, Machine Learning tools

### User Statistics
Displays comprehensive metrics:
- Total commits and contributions
- Pull requests and issues created  
- Stars gained across repositories
- Repository counts (owned vs contributed)

### Programming Language Rankings
Visual representation of:
- Language usage percentages
- Lines of code and bytes analysis
- Repository-based language detection

### GitHub API Integration
Fetches real-time data:
- Live repository information from GitHub API
- Actual language statistics and byte counts
- Intelligent fallback to static data when API unavailable
- Authenticated requests for higher rate limits

## 🔧 Quick Start

### Basic Usage (Unauthenticated)
```bash
python3 script.py
```

### Authenticated Usage (Recommended)
```bash
export GIT_TOKEN="your_token_here"
python3 script.py
```

## 🔐 GitHub API Authentication Setup

For best results and to avoid rate limiting, set up a GitHub Personal Access Token.

### Creating a GitHub Personal Access Token

1. **Go to GitHub Settings**
   - Navigate to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
   - Or: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate New Token**
   - Click "Generate new token" → "Generate new token (classic)"
   - Give it a descriptive name like "Repository Stats Script"

3. **Configure Token Permissions**
   Select the following scopes:
   - ✅ `public_repo` - Access public repositories
   - ✅ `read:user` - Read user profile data
   - ✅ `read:org` - Read organization data (if analyzing org repos)

4. **Generate and Copy Token**
   - Click "Generate token"
   - **Copy the token immediately** (you won't see it again!)

### Setting Up the Token

#### Option 1: Environment Variable (Local Development)
```bash
export GIT_TOKEN="your_token_here"
python3 script.py
```

#### Option 2: GitHub Actions Secret (Recommended for CI/CD)
1. **Add Repository Secret**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GIT_TOKEN`
   - Value: Your personal access token

2. **Update GitHub Actions Workflow**
   ```yaml
   - name: Run Repository Stats Script
     env:
       GIT_TOKEN: ${{ secrets.GIT_TOKEN }}
     run: python3 script.py
   ```

#### Option 3: .env File (Local Development)
Create a `.env` file in the project root:
```
GIT_TOKEN=your_token_here
```

Then run:
```bash
source .env
python3 script.py
```

### Authentication Status Indicators

When you run the script:

**✅ With token:**
```
✅ GitHub API authentication enabled
🔍 Fetching repositories for user: username (✅ authenticated)
```

**⚠️ Without token:**
```
⚠️ No GitHub token found. API requests may be rate limited.
   Set GIT_TOKEN environment variable for authenticated access.
🔍 Fetching repositories for user: username (⚠️ unauthenticated)
```

## 📊 Output

The script generates two files:
- `language_ranking.json` - Raw data in JSON format
- `language_ranking.md` - Formatted markdown report with tech stack, user statistics, and language rankings

### Sample Output
The script automatically detects frameworks from repository names (e.g., "LeptosTest" → Leptos framework) and generates a comprehensive profile report.

Example generated content:
- 🚀 **Tech Stack** with categorized technologies
- 📊 **User Statistics** table with metrics
- 🔥 **Programming Language Rankings** with visual progress bars

## 🔍 Framework Detection

The script intelligently detects frameworks and technologies based on:
- Repository names (e.g., "DioxusTest" → Dioxus framework)
- Language patterns
- Project indicators

### Supported Technologies:
- **Rust**: Leptos, Dioxus, Sycamore, Actix, Tokio, Axum, GPUI
- **Java**: Spring Framework, Apache Kafka, Microservices
- **Dart**: Flutter, Material Design
- **Frontend**: React, Vue.js, TypeScript/JavaScript
- **Data Science**: Python, Machine Learning

## 📡 Data Sources

### GitHub API (Primary)
- ✅ Real-time repository data
- ✅ Actual language statistics from GitHub's linguist
- ✅ Live byte counts and language detection
- ✅ Automatic updates when repositories change

### Static Fallback (Secondary)
- 📂 Used when API is unavailable (network restrictions)
- 📂 Manually curated repository list
- 📂 Estimated language statistics
- 📂 Ensures script always produces output

## ⚙️ Configuration

### Excluding Repositories
Create a `config.json` file to exclude specific repositories:

```json
{
  "excluded_repositories": [
    {"name": "test-repo"},
    {"name": "private-repo"}
  ],
  "excluded_languages": ["HTML", "CSS", "Makefile"],
  "included_organizations": [],
  "included_contributors": []
}
```

### Supported Environment Variables
The script looks for tokens in this priority order:
1. `GIT_TOKEN` (Primary - recommended for GitHub restrictions)
2. `GITHUB_TOKEN` (Fallback)
3. `GH_TOKEN` (Secondary fallback)

## 🔄 Repository Updates

The script now automatically fetches fresh repository data from GitHub every time it runs:

**✅ Benefits:**
- Always gets current repository information
- Uses real language statistics from GitHub
- Works in both open and restricted environments  
- Maintains all existing functionality
- Zero breaking changes to output format

## 🚀 Usage in GitHub Actions

Add to your workflow:
```yaml
name: Update Profile Stats
on:
  schedule:
    - cron: '0 0 * * 0' # Weekly on Sunday
  workflow_dispatch: # Manual trigger

jobs:
  update-stats:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.x'
        
    - name: Install dependencies
      run: pip install requests
      
    - name: Update Profile Stats
      env:
        GIT_TOKEN: ${{ secrets.GIT_TOKEN }}
      run: python3 script.py
      
    - name: Commit results
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add language_ranking.json language_ranking.md
        git commit -m "Update profile statistics" || exit 0
        git push
```

## 🛡️ Security Best Practices

- ✅ **Never commit tokens to Git** - Add `.env` to `.gitignore`
- ✅ **Use repository secrets** for GitHub Actions
- ✅ **Set minimal required permissions** on tokens
- ✅ **Regularly rotate tokens** (every 90 days recommended)
- ✅ **Revoke unused tokens** from GitHub settings

## 🚨 Troubleshooting

### "401 Unauthorized" Error
- Token is invalid or expired
- Token doesn't have required permissions
- Double-check the token value

### "403 Forbidden" Error
- Rate limit exceeded (authenticated requests have higher limits)
- Repository access denied
- Organization permissions required

### "API blocked by network proxy"
- Corporate firewall blocking GitHub API
- Token authentication may bypass some proxy restrictions
- Script automatically falls back to static data

## 📋 Dependencies

```bash
pip install requests
```

## 🔧 Installation

1. Clone this repository
2. Install dependencies: `pip install requests`
3. (Optional) Set up GitHub token for authentication
4. Run: `python3 script.py`

## 📈 What Gets Analyzed

The script analyzes:
- **All your public repositories** (owned)
- **Organization repositories** where you're a contributor
- **Language usage** with actual byte counts from GitHub
- **Framework detection** from repository names
- **Comprehensive statistics** about your GitHub activity

Generated files include complete tech stack categorization, user metrics, and language rankings with visual progress bars.