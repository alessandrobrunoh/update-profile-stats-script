# 🚀 GitHub Profile Stats Auto-Updater - User Setup Guide

Transform your GitHub profile with automatically generated statistics that update daily! This tool analyzes your repositories and creates beautiful, data-driven content for your README.md.

## ✨ What This Does

- 📊 **Analyzes all your repositories** for languages, frameworks, and code quality
- 🤖 **Generates beautiful profile statistics** using AI-powered analysis
- 📝 **Updates your README.md automatically** with fresh data
- ⏰ **Runs daily** to keep your profile current
- 🎨 **Creates professional visualizations** of your coding activity

## 🎯 Quick Start (5 Minutes Setup)

### Step 1: Copy the Workflow File
1. In your GitHub profile repository, create the directory structure: `.github/workflows/`
2. Copy the contents of [`example-workflow-for-users.yml`](https://raw.githubusercontent.com/alessandrobrunoh/update-profile-stats-script/refs/heads/main/example-workflow-for-users.yml)
3. Save it as `.github/workflows/update-stats.yml`

### Step 2: Set Up Required Secrets
Go to your repository **Settings** → **Secrets and variables** → **Actions** and add:

#### 🔑 GITHUB_TOKEN
- Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
- Click "Generate new token (classic)"
- Give it a descriptive name like "Profile Stats Generator"
- Select scopes: `repo` (Full control of private repositories)
- Copy the generated token
- Add it as a secret named `GITHUB_TOKEN`

#### 🤖 GEMINI_API_KEY
- Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
- Create a new API key
- Copy the API key
- Add it as a secret named `GEMINI_API_KEY`

### Step 3: Enable and Run
1. Commit the workflow file to your repository
2. Go to the **Actions** tab in your repository
3. Enable GitHub Actions if prompted
4. Click on "Update Profile Stats" workflow
5. Click "Run workflow" to test it immediately

## 🔧 Configuration Options

The workflow automatically downloads and configures everything for your account. However, you can customize:

### Schedule
Change when the workflow runs by modifying the cron expression:
```yaml
schedule:
  - cron: "0 2 * * *"  # 2 AM UTC daily
```

Common schedules:
- `"0 */6 * * *"` - Every 6 hours
- `"0 0 * * 0"` - Weekly on Sundays
- `"0 0 1 * *"` - Monthly on the 1st

### Repository Exclusions
The script automatically excludes common repositories, but you can customize this by:
1. Creating your own `config.toml` file in your repository
2. Modifying the workflow to use your custom config instead of downloading the default

## 📋 Example Generated Output

Your README.md will be automatically updated with sections like:

- 📊 **Language Statistics** - Breakdown of your most-used programming languages
- 🏆 **Top Technologies** - Frameworks and tools you work with
- 📈 **Repository Analysis** - Quality metrics and activity patterns
- 🎯 **Professional Summary** - AI-generated insights about your coding style
- 📅 **Last Updated** - Timestamp of the latest analysis

## 🔍 How It Works

1. **Daily Trigger**: The workflow runs automatically at 2 AM UTC
2. **Script Download**: Downloads the latest analysis script from this repository
3. **Repository Analysis**: Scans all your public repositories
4. **AI Processing**: Uses Google Gemini to analyze code quality and patterns
5. **Markdown Generation**: Creates formatted statistics and insights
6. **Auto-Commit**: Updates your README.md with the new content

## 🚨 Troubleshooting

### Common Issues

**❌ "GEMINI_API_KEY environment variable not set"**
- Solution: Make sure you've added the `GEMINI_API_KEY` secret in repository settings

**❌ "API requests may be rate-limited"**
- Solution: Verify your `GITHUB_TOKEN` secret is set correctly with `repo` permissions

**❌ Workflow doesn't run automatically**
- Solution: Check that the workflow file is in `.github/workflows/` and committed to your main branch

**❌ No changes detected**
- Solution: This is normal if your repositories haven't changed since the last run

### Getting Help

1. Check the **Actions** tab for detailed logs of each workflow run
2. Verify your secrets are set correctly in repository settings
3. Ensure your GitHub token has the necessary permissions
4. Make sure your Gemini API key is valid and has quota remaining

## 🔐 Security & Privacy

- **Your secrets are secure**: GitHub encrypts all secrets and only provides them to authorized workflows
- **Read-only access**: The script only reads your repository data, never modifies your code
- **Open source**: You can review all code in this repository before using
- **No data collection**: Your repository data is processed locally in GitHub Actions

## 🎨 Customization Ideas

Once you have the basic setup working, you can:
- Modify the generated markdown templates
- Add custom sections to your README
- Integrate with other profile enhancement tools
- Create custom visualizations using the generated data

## 📞 Support

- 🐛 **Bug Reports**: Open an issue in this repository
- 💡 **Feature Requests**: Suggest improvements via GitHub issues
- 📖 **Documentation**: Check the main repository README for advanced configuration
- 🤝 **Community**: Share your customizations and help others

---

**Made with ❤️ by [@alessandrobrunoh](https://github.com/alessandrobrunoh)**

*Last updated: 2024*