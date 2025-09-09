# GitHub Token Setup Guide

To enable GitHub API authentication and fetch real-time repository data, you need to set up a GitHub Personal Access Token.

## 🔐 Creating a GitHub Personal Access Token

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

## 🔧 Setting Up the Token

### Option 1: Environment Variable (Local Development)

```bash
export GITHUB_TOKEN="your_token_here"
python3 script.py
```

### Option 2: GitHub Actions Secret (Recommended for CI/CD)

1. **Add Repository Secret**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GITHUB_TOKEN`
   - Value: Your personal access token

2. **Update GitHub Actions Workflow**
   ```yaml
   - name: Run Repository Stats Script
     env:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
     run: python3 script.py
   ```

### Option 3: .env File (Local Development)

Create a `.env` file in the project root:
```
GITHUB_TOKEN=your_token_here
```

Then run:
```bash
source .env
python3 script.py
```

## 🔍 Verifying Token Setup

When you run the script with a valid token, you'll see:
```
✅ GitHub API authentication enabled
🚀 Attempting to fetch repositories from GitHub API...
🔍 Fetching repositories for user: username (✅ authenticated)
📊 Found X repositories via GitHub API
```

Without a token, you'll see:
```
⚠️  No GitHub token found. API requests may be rate limited.
   Set GITHUB_TOKEN environment variable for authenticated access.
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
- Contact IT administrator if issue persists

## 📋 Token Requirements Summary

**Minimum Required Scopes:**
- `public_repo` - Read public repository data
- `read:user` - Read user profile information

**Optional Scopes:**
- `read:org` - Read organization repository data
- `repo` - Full repository access (only if you need private repos)

## 🔄 Token Refresh

Personal Access Tokens (classic) don't expire automatically, but it's recommended to:
- Review and rotate tokens every 90 days
- Remove unused tokens
- Use fine-grained tokens where possible for better security