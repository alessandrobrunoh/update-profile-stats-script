# GitHub Profile Stats Script

A Python script that automatically generates comprehensive GitHub profile statistics including tech stack categorization, user metrics, and programming language rankings using real-time GitHub API data.

## 🚀 Features

### Auto Update Action Workflow
Automatically update the README.md every night.

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

## 🔐 1. GitHub API Authentication Setup

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

#### GitHub Actions Secret
1. **Add Repository Secret**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GIT_TOKEN`
   - Value: Your personal access token
  
2. **Copy GitHub Actions Workflow in your Repo**

3. **Run the GitHub Actions Workflow**

4. **Enjoy your new Profile**

*⭐ Thanks, for using this script, if you appreciate it, please consider starring the repositor!*
