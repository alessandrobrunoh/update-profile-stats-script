# update-profile-stats-script

A Python script that automatically generates comprehensive GitHub profile statistics including tech stack categorization, user metrics, and programming language rankings using real-time GitHub API data.

## Features

🚀 **Tech Stack Category Generation** - Automatically categorizes and displays your technologies:
- **Primary Technologies**: Rust, Java, Dart with framework detection
- **Additional Technologies**: Frontend development tools (React, Vue.js, SCSS/CSS)
- **Data & Analytics**: Python, Machine Learning tools

📊 **User Statistics** - Displays comprehensive metrics:
- Total commits and contributions
- Pull requests and issues created  
- Stars gained across repositories
- Repository counts (owned vs contributed)

🔥 **Programming Language Rankings** - Visual representation of:
- Language usage percentages
- Lines of code and bytes analysis
- Repository-based language detection

🔗 **GitHub API Integration** - Fetches real-time data:
- Live repository information from GitHub API
- Actual language statistics and byte counts
- Intelligent fallback to static data when API unavailable
- Authenticated requests for higher rate limits

## Quick Start

### Basic Usage (Unauthenticated)
```bash
python3 script.py
```

### Authenticated Usage (Recommended)
```bash
export GITHUB_TOKEN="your_token_here"
python3 script.py
```

## 🔐 GitHub API Authentication

For best results and to avoid rate limiting, set up a GitHub Personal Access Token:

1. **[Create a GitHub token](https://github.com/settings/tokens)** with `public_repo` scope
2. **Set environment variable**: `export GITHUB_TOKEN="your_token"`
3. **Run the script**: `python3 script.py`

📖 **Detailed setup guide**: [GITHUB_TOKEN_SETUP.md](./GITHUB_TOKEN_SETUP.md)

### Authentication Status
- ✅ **With token**: `GitHub API authentication enabled`
- ⚠️ **Without token**: `No GitHub token found. API requests may be rate limited.`

## Output

The script generates:
- `language_ranking.json` - Raw data in JSON format
- `language_ranking.md` - Formatted markdown report

## Output Example

The script automatically detects frameworks from repository names (e.g., "LeptosTest" → Leptos framework) and generates a comprehensive profile report including tech stack, user statistics, and language rankings.

## Framework Detection

The script intelligently detects frameworks and technologies based on:
- Repository names (e.g., "DioxusTest" → Dioxus framework)
- Language patterns
- Project indicators

Supported framework categories:
- **Rust**: Leptos, Dioxus, Sycamore, Actix, Tokio, Axum, GPUI
- **Java**: Spring Framework, Apache Kafka, Microservices
- **Dart**: Flutter, Material Design
- **Frontend**: React, Vue.js, TypeScript/JavaScript
- **Data Science**: Python, Machine Learning

## Data Sources

### GitHub API (Primary)
- ✅ Real-time repository data
- ✅ Actual language statistics from GitHub's linguist
- ✅ Live byte counts and language detection
- ✅ Automatic updates when repositories change

### Static Fallback (Secondary)
- 📂 Used when API is unavailable
- 📂 Manually curated repository list
- 📂 Estimated language statistics
- 📂 Ensures script always produces output

## Usage in GitHub Actions

Add to your workflow:
```yaml
- name: Update Profile Stats
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: python3 script.py
```

## Dependencies

```bash
pip install requests
```