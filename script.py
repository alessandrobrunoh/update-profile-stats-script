import os
import sys
import subprocess
import time
import base64
import random
import json
import google.generativeai as genai
from collections import defaultdict
from datetime import datetime

def ensure_dependencies():
    """
    Ensure all required packages are available, installing them if needed.
    """
    required_packages = [
        ("requests>=2.31.0", "requests"),
        ("tomli>=2.0.0", "tomli"),
        ("python-dotenv>=1.0.0", "dotenv"),
        ("google-generativeai>=0.3.0", "google.generativeai"),
        ("pytz>=2023.3", "pytz")
    ]

    print("🔍 Checking dependencies...")

    missing_packages = []
    for package_spec, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✅ {import_name} is available")
        except ImportError:
            missing_packages.append(package_spec)
            print(f"❌ {import_name} is missing")

    if missing_packages:
        print(f"\n📦 Installing {len(missing_packages)} missing packages...")
        try:
            # Install packages one by one for better error handling
            for package_spec in missing_packages:
                print(f"  Installing {package_spec}...")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    "--quiet", "--disable-pip-version-check", package_spec
                ])

            print("✅ All packages installed successfully!")

            # Force Python to recognize newly installed packages
            import importlib
            importlib.invalidate_caches()

            # Re-check imports after installation
            print("🔍 Verifying installations...")
            all_available = True
            for package_spec, import_name in required_packages:
                if package_spec in missing_packages:
                    try:
                        # Try importing with a clean slate
                        if import_name in sys.modules:
                            del sys.modules[import_name]
                        __import__(import_name)
                        print(f"✅ {import_name} is now available")
                    except ImportError:
                        print(f"⚠️ {import_name} installed but may need environment refresh")
                        all_available = False

            if not all_available and os.getenv('CI'):
                print("🔄 In CI environment - packages should be available for import")

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            print("\n💡 Please install manually using:")
            print(f"   pip install {' '.join(missing_packages)}")
            sys.exit(1)
    else:
        print("✅ All dependencies are available!")

# Auto-install required packages (replaces requirements.txt)
ensure_dependencies()

# Import packages (they're already imported by ensure_dependencies, but we'll do it explicitly for clarity)
import pytz
import requests
import tomli
from dotenv import load_dotenv
from dotenv import load_dotenv

# Load environment variables from .env file at the start
load_dotenv()

class GitHubLanguageAnalyzer:
    def __init__(self, username=None, use_simulation=False, config_path="config.toml"):
        """
        Initializes the analyzer with GitHub credentials and settings.
        """
        self.config = self.load_config(config_path)

        # Auto-detect username from multiple sources
        detected_username = (
            username or
            self.config.get("github", {}).get("username") or
            os.getenv("GITHUB_REPOSITORY_OWNER") or  # GitHub Actions environment
            os.getenv("GITHUB_ACTOR") or            # GitHub Actions actor
            self._extract_username_from_repo() or   # From GITHUB_REPOSITORY
            "default-user"
        )

        self.username = detected_username
        if self.username != "default-user":
            print(f"🔍 Using GitHub username: {self.username}")
        else:
            print("⚠️ Could not detect GitHub username. Using default.")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.use_simulation = use_simulation

        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        self.repositories = []
        self.repo_cache = {}
        self.tech_stack_mapping = self.get_tech_stack_mapping()
        self.ai_cache = self.load_ai_cache()

        if not self.github_token:
            print("Warning: GITHUB_TOKEN environment variable not set. API requests may be rate-limited.")

        if not self.gemini_api_key:
            print("Warning: GEMINI_API_KEY not set. AI-based summaries will be disabled.")
            self.gemini_model = None
        else:
            genai.configure(api_key=self.gemini_api_key)
            gemini_model_name = self.config.get("gemini", {}).get("model", "gemini-1.5-flash")
            self.gemini_model = genai.GenerativeModel(gemini_model_name)

    def load_ai_cache(self, cache_path="ai_cache.json"):
        """
        Loads the AI summary cache from a JSON file.
        """
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_ai_cache(self, cache_path="ai_cache.json"):
        """
        Saves the AI summary cache to a JSON file.
        """
        with open(cache_path, "w") as f:
            json.dump(self.ai_cache, f, indent=4)

    def load_config(self, config_path="config.toml"):
        """
        Loads configuration from a TOML file.
        """
        try:
            with open(config_path, "rb") as f:
                return tomli.load(f)
        except FileNotFoundError:
            print(f"Warning: Configuration file not found at '{config_path}'. Using default settings.")
            return {}
        except tomli.TOMLDecodeError as e:
            print(f"Error: Could not decode the TOML file at '{config_path}': {e}")
            return {}

    def _extract_username_from_repo(self):
        """
        Extract username from GITHUB_REPOSITORY environment variable (format: owner/repo).
        """
        github_repo = os.getenv("GITHUB_REPOSITORY")
        if github_repo and "/" in github_repo:
            return github_repo.split("/")[0]
        return None

    def _make_github_request(self, url, params=None, retries=3, delay=5):
        """
        Makes a request to the GitHub API with rate limit handling.
        """
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    sleep_duration = max(reset_time - time.time(), 0) + 10
                    print(f"Rate limit exceeded. Waiting for {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    return None

    def fetch_user_repositories(self):
        """
        Fetches all public repositories for the configured user.
        """
        if self.use_simulation:
            print("Simulation mode: Using mock repository data.")
            return [{"name": f"sim-repo-{i}", "fork": False, "languages_url": ""} for i in range(5)]

        print(f"Fetching last 100 repositories for user: {self.username}")
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/users/{self.username}/repos"
            params = {"per_page": 100, "page": page, "sort": "pushed", "direction": "desc"}
            page_repos = self._make_github_request(url, params=params)
            if not page_repos:
                break
            repos.extend(page_repos)
            if len(repos) >= 100 or len(page_repos) < 100:
                break
            page += 1

        repos = repos[:100]

        exclude_repos = self.config.get("github", {}).get("exclude_repos", [])
        self.repositories = [repo for repo in repos if not repo['fork'] and repo['name'] not in exclude_repos]
        print(f"Found {len(self.repositories)} non-forked repositories.")
        return self.repositories

    def fetch_repository_languages(self, repo_name, structure_analysis):
        """
        Fetches language data for a specific repository with generated code filtering.
        """
        try:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
            raw_languages = self._make_github_request(url) or {}

            if not raw_languages:
                print(f"Warning: No language data available for {repo_name} (may be private or empty)")
                return {}

            # Filter out excluded languages
            excluded_languages = set(self.config.get("github", {}).get("exclude_languages", []))
            filtered_languages = {
                lang: bytes_count for lang, bytes_count in raw_languages.items()
                if lang not in excluded_languages
            }

            # If enabled, check for generated code and adjust language stats
            if self.config.get("github", {}).get("exclude_generated_code", True):
                filtered_languages = self._filter_generated_code_languages(repo_name, filtered_languages, structure_analysis)

            return filtered_languages
        except Exception as e:
            print(f"Warning: Could not fetch languages for {repo_name}: {e}")
            return {}

    def _filter_generated_code_languages(self, repo_name, languages, repo_structure):
        """
        Analyzes repository structure and filters out generated code from language stats.
        """
        try:
            # Validate repository name first
            if not repo_name or not repo_name.strip():
                print(f"Warning: Cannot filter generated code for invalid repository name")
                return languages

            # Get repository structure is now passed in
            generated_patterns = self.config.get("exclusions", {}).get("generated_code_patterns", [])
            framework_files = self.config.get("exclusions", {}).get("framework_generated_files", [])

            # Analyze key files to detect generation patterns
            total_generated_bytes = {}

            for file_info in repo_structure.get("analyzed_files", []):
                file_path = file_info.get("path", "")
                file_content = file_info.get("content", "")

                # Check if file matches generated file patterns
                is_generated = self._is_generated_file(file_path, file_content, generated_patterns, framework_files)

                if is_generated:
                    # Estimate language and bytes for this generated file
                    file_lang = self._detect_file_language(file_path)
                    if file_lang in languages:
                        estimated_bytes = len(file_content.encode('utf-8'))
                        total_generated_bytes[file_lang] = total_generated_bytes.get(file_lang, 0) + estimated_bytes

            # Subtract estimated generated bytes from language totals
            filtered_languages = {}
            for lang, total_bytes in languages.items():
                generated_bytes = total_generated_bytes.get(lang, 0)
                # Keep at least 10% of original bytes to avoid completely removing languages
                adjusted_bytes = max(total_bytes - generated_bytes, total_bytes * 0.1)
                if adjusted_bytes > 0:
                    filtered_languages[lang] = int(adjusted_bytes)

            return filtered_languages

        except Exception as e:
            print(f"Warning: Could not filter generated code for {repo_name}: {e}")
            return languages

    def _is_generated_file(self, file_path, content, generated_patterns, framework_files):
        """
        Determines if a file appears to be generated or scaffolded.
        """
        # Check file path patterns
        for pattern in framework_files:
            if self._matches_pattern(file_path, pattern):
                return True

        # Check content for generation markers
        content_lower = content.lower()
        for pattern in generated_patterns:
            if pattern.lower() in content_lower:
                return True

        # AI detection removed.

        return False



    def _detect_file_language(self, file_path):
        """
        Detects programming language from file extension.
        """
        extension_map = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.java': 'Java', '.cpp': 'C++', '.c': 'C', '.cs': 'C#',
            '.go': 'Go', '.rs': 'Rust', '.php': 'PHP', '.rb': 'Ruby',
            '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
            '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
            '.sql': 'SQL', '.sh': 'Shell', '.yml': 'YAML', '.yaml': 'YAML'
        }

        for ext, lang in extension_map.items():
            if file_path.lower().endswith(ext):
                return lang
        return 'Other'

    def _matches_pattern(self, file_path, pattern):
        """
        Checks if file path matches a glob-like pattern.
        """
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)

    def _is_repository_accessible(self, repo_name):
        """
        Checks if a repository is accessible (not private, not deleted, etc.)
        """
        try:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}"
            response = self._make_github_request(url)
            return response is not None and not response.get("private", False)
        except Exception as e:
            print(f"Warning: Could not check accessibility for {repo_name}: {e}")
            return False



    def analyze_repository_structure(self, repo_name):
        """
        Analyzes a repository's structure, files, and estimates code quality using Gemini.
        """
        # Validate repository name
        if not repo_name or not repo_name.strip():
            print(f"Warning: Invalid repository name (empty or None), skipping analysis")
            return self._get_fallback_repo_data("unknown")

        repo_name = repo_name.strip()
        print(f"Analyzing repository structure for: {repo_name}")

        if self.use_simulation:
            return self._simulate_repository_analysis(repo_name)

        contents = self._get_repository_contents(repo_name)
        if not contents:
            print(f"Warning: Could not fetch contents for {repo_name}, using fallback data")
            return self._get_fallback_repo_data(repo_name)

        total_files = 0
        total_lines = 0
        quality_scores = []

        exclude_files = self.config.get("exclusions", {}).get("exclude_files", [])

        for item in contents:
            if item['type'] == 'file' and not self._should_exclude_file(item['path'], exclude_files):
                total_files += 1
                # Limit file size to avoid excessive API usage/cost
                if item['size'] > 100000: # 100KB limit
                    print(f"Skipping large file: {item['path']}")
                    continue

                file_content = self._get_file_content(item['url'])
                if file_content:
                    lines = file_content.count('\n') + 1
                    total_lines += lines

                    # AI quality score removed.
                    quality_scores.append(0) # Append a default value

        # Calculate overall quality from Gemini scores
        overall_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        return {
            "repo_name": repo_name,
            "total_files": total_files,
            "total_lines": total_lines,
            "overall_quality_score": overall_quality_score,
        }

    def _get_repository_contents(self, repo_name):
        """
        Retrieves the file and directory structure of a repository.
        """
        if repo_name in self.repo_cache:
            return self.repo_cache[repo_name]

        contents = self._fetch_repo_contents_from_api(repo_name)
        self.repo_cache[repo_name] = contents
        return contents

    def _fetch_repo_contents_from_api(self, repo_name):
        """
        Fetches repository contents recursively from the GitHub API.
        """
        try:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}/git/trees/main?recursive=1"
            data = self._make_github_request(url)
            if not data or 'tree' not in data:
                print(f"Warning: Repository {repo_name} may be private, empty, or use a different default branch")
                return []
        except Exception as e:
            print(f"Warning: Could not access repository {repo_name}: {e}")
            return []

        exclude_dirs = self.config.get("exclusions", {}).get("exclude_dirs", [])

        # Filter out excluded directories at the beginning
        filtered_tree = [
            item for item in data['tree']
            if not any(excluded_dir in item['path'] for excluded_dir in exclude_dirs)
        ]
        return filtered_tree

    def _get_latest_commit_sha(self, repo_name):
        """
        Gets the latest commit SHA for a repository's default branch.
        """
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/branches/main" # Assumes main branch
        data = self._make_github_request(url)
        if data and 'commit' in data and 'sha' in data['commit']:
            return data['commit']['sha']
        return None

    def _get_file_content(self, file_url):
        """
        Retrieves the content of a file from its API URL.
        """
        data = self._make_github_request(file_url)
        if data and 'content' in data:
            try:
                return base64.b64decode(data['content']).decode('utf-8')
            except (UnicodeDecodeError, ValueError):
                return None # Could be a binary file
        return None

    def _simulate_repository_analysis(self, repo_name):
        """
        Generates simulated analysis data for a repository.
        """
        return {
            "repo_name": repo_name,
            "total_files": random.randint(10, 100),
            "total_lines": random.randint(1000, 10000),
            "overall_quality_score": random.uniform(60, 95),
        }

    def _ai_summarize_repository(self, repo_name):
        """
        Uses Gemini to generate a one-sentence summary of a repository, with caching.
        """
        if not self.gemini_model:
            return "An open-source project."

        latest_sha = self._get_latest_commit_sha(repo_name)
        if not latest_sha:
            return "An open-source project."

        # Check cache
        if self.ai_cache.get(repo_name, {}).get('sha') == latest_sha:
            print(f"Using cached summary for {repo_name}")
            return self.ai_cache[repo_name]['summary']

        print(f"Generating new AI summary for {repo_name}...")

        contents = self._get_repository_contents(repo_name)
        if not contents:
            return "An open-source project."

        readme_content = ""
        for item in contents:
            if item['path'].lower() == 'readme.md':
                readme_content = self._get_file_content(item['url'])
                break

        file_list = "\n".join([f"- {item['path']}" for item in contents[:20]])

        prompt = f"""Analyze the following repository structure and README to generate a concise, one-sentence summary of the project's purpose.

**Repository Name:** {repo_name}

**File Structure:**
{file_list}

**README:**
{readme_content[:1000]}

**Summary (one sentence):**
"""

        try:
            response = self.gemini_model.generate_content(prompt)
            summary = response.text.strip()

            # Update cache
            self.ai_cache[repo_name] = {'sha': latest_sha, 'summary': summary}

            return summary
        except Exception as e:
            print(f"AI summary generation failed for {repo_name}: {e}")
            return "An open-source project."

    def _should_exclude_file(self, file_path, exclude_list):
        """
        Checks if a file should be excluded based on the configuration.
        """
        return os.path.basename(file_path) in exclude_list



    def _get_fallback_repo_data(self, repo_name):
        """
        Provides fallback data for a repository that couldn't be analyzed.
        """
        return {
            "repo_name": repo_name,
            "total_files": 0,
            "total_lines": 0,
            "overall_quality_score": 0,
        }

    def get_user_repositories(self):
        """
        Public method to get the fetched list of repositories.
        """
        if not self.repositories:
            self.fetch_user_repositories()
        return self.repositories

    def refresh_repositories(self):
        """
        Clears the current repository list and fetches it again.
        """
        self.repositories = []
        self.fetch_user_repositories()

    def get_tech_stack_mapping(self):
        """
        Defines the mapping from keywords to technology names and icons.
        This could be moved to the config.toml file in the future.
        """
        return {
            "react": ("React", "react"),
            "vue": ("Vue.js", "vuejs"),
            "angular": ("Angular", "angular"),
            "django": ("Django", "django"),
            "flask": ("Flask", "flask"),
            "spring": ("Spring", "spring"),
            "express": ("Express.js", "express"),
            "laravel": ("Laravel", "laravel"),
            "rubyonrails": ("Ruby on Rails", "rails"),
            "fastapi": ("FastAPI", "fastapi"),
            "next.js": ("Next.js", "nextjs"),
            "nuxt.js": ("Nuxt.js", "nuxtjs"),
            "gatsby": ("Gatsby", "gatsby"),
            "svelte": ("Svelte", "svelte"),
            "docker": ("Docker", "docker"),
            "kubernetes": ("Kubernetes", "kubernetes"),
            "terraform": ("Terraform", "terraform"),
            "ansible": ("Ansible", "ansible"),
            "aws": ("AWS", "amazonwebservices"),
            "azure": ("Azure", "azure"),
            "gcp": ("Google Cloud", "googlecloud"),
            "jest": ("Jest", "jest"),
            "pytest": ("Pytest", "pytest"),
            "junit": ("JUnit", "junit"),
            "mocha": ("Mocha", "mocha"),
            "cypress": ("Cypress", "cypress"),
            "selenium": ("Selenium", "selenium"),
            "webpack": ("Webpack", "webpack"),
            "babel": ("Babel", "babel"),
            "vite": ("Vite", "vite"),
            "tailwind": ("Tailwind CSS", "tailwindcss"),
            "bootstrap": ("Bootstrap", "bootstrap"),
            "sass": ("Sass", "sass"),
            "less": ("Less", "less"),
            "graphql": ("GraphQL", "graphql"),
            "redis": ("Redis", "redis"),
            "mongodb": ("MongoDB", "mongodb"),
            "postgresql": ("PostgreSQL", "postgresql"),
            "mysql": ("MySQL", "mysql"),
            "sqlite": ("SQLite", "sqlite"),
            "kafka": ("Apache Kafka", "apachekafka"),
            "rabbitmq": ("RabbitMQ", "rabbitmq"),
            "nginx": ("Nginx", "nginx"),
            "apache": ("Apache", "apache"),
            "jenkins": ("Jenkins", "jenkins"),
            "github actions": ("GitHub Actions", "githubactions"),
            "gitlab": ("GitLab CI", "gitlab"),
            "circleci": ("CircleCI", "circleci"),
            "travisci": ("Travis CI", "travisci"),
            "electron": ("Electron", "electron"),
            "react native": ("React Native", "react"),
            "flutter": ("Flutter", "flutter"),
            "dart": ("Dart", "dart"),
            "swift": ("Swift", "swift"),
            "kotlin": ("Kotlin", "kotlin"),
            "rust": ("Rust", "rust"),
            "go": ("Go", "go"),
            "python": ("Python", "python"),
            "java": ("Java", "java"),
            "javascript": ("JavaScript", "javascript"),
            "typescript": ("TypeScript", "typescript"),
            "csharp": ("C#", "csharp"),
            "cpp": ("C++", "cplusplus"),
            "php": ("PHP", "php"),
            "ruby": ("Ruby", "ruby"),
            "html": ("HTML5", "html5"),
            "css": ("CSS3", "css3"),
        }

    def detect_frameworks_from_repos(self, analysis_results):
        """
        Detects frameworks and technologies from repository contents and filenames.
        """
        detected_tech = set()
        repo_names = [res["repo_name"] for res in analysis_results]

        for tech_key in self.tech_stack_mapping.keys():
            # Check in repo names
            if any(tech_key in name.lower() for name in repo_names):
                detected_tech.add(tech_key)

            # Check in file paths from cache
            for repo_name in self.repo_cache:
                contents = self.repo_cache.get(repo_name, [])
                for item in contents:
                    path_lower = item['path'].lower()
                    if tech_key in path_lower:
                        detected_tech.add(tech_key)
                        break # Move to next repo once found
                if tech_key in detected_tech:
                    continue

        return list(detected_tech)

    def generate_project_showcase_md(self, analysis_results):
        """
        Generates a markdown showcase for the top projects with AI summaries.
        """
        if not analysis_results:
            return ""

        markdown = "## 🚀 Project Showcase\n\n"

        # Select top 3 projects by total lines of code
        sorted_repos = sorted(analysis_results, key=lambda x: x.get('total_lines', 0), reverse=True)

        for repo_analysis in sorted_repos[:3]:
            repo_name = repo_analysis['repo_name']

            summary = self._ai_summarize_repository(repo_name)

            languages = repo_analysis.get('languages', {})
            detected_tech = self.detect_frameworks_from_repos([repo_analysis])

            markdown += f"### [{repo_name}](https://github.com/{self.username}/{repo_name})\n"
            markdown += f"*{summary}*\n\n"

            markdown += "<p>"
            for lang in languages:
                badge = self._format_tech_badge(lang, self._get_language_logo(lang))
                markdown += f"{badge} "

            for tech_key in detected_tech:
                if tech_key in self.tech_stack_mapping:
                    display_name, icon_name = self.tech_stack_mapping[tech_key]
                    badge = self._format_tech_badge(display_name, icon_name)
                    markdown += f"{badge} "
            markdown += "</p>\n\n"

        return markdown

    def _format_tech_badge(self, name, icon):
        """
        Creates a beautiful technology badge with proper styling.
        """
        # Clean name for URL
        clean_name = name.replace(" ", "%20").replace(".", "%2E")
        color = self._get_tech_color(name)

        return f"![{name}](https://img.shields.io/badge/{clean_name}-{color}?style=for-the-badge&logo={icon}&logoColor=white)"

    def _get_tech_color(self, tech_name):
        """
        Returns appropriate colors for technology badges.
        """
        color_map = {
            "React": "61DAFB",
            "Vue.js": "4FC08D",
            "Angular": "DD0031",
            "Django": "092E20",
            "Flask": "000000",
            "Spring": "6DB33F",
            "Express.js": "000000",
            "Laravel": "FF2D20",
            "Next.js": "000000",
            "Docker": "2496ED",
            "Kubernetes": "326CE5",
            "AWS": "FF9900",
            "Azure": "0078D4",
            "Google Cloud": "4285F4",
            "Python": "3776AB",
            "JavaScript": "F7DF1E",
            "TypeScript": "3178C6",
            "Java": "ED8B00",
            "Go": "00ADD8"
        }
        return color_map.get(tech_name, "6E7781")

    def _format_tech_display(self, name, icon, theme='dark'):
        """
        Legacy method - kept for compatibility.
        """
        return self._format_tech_badge(name, icon)

        # Special handling for some icons that look better with specific colors
        if icon in ["javascript", "python", "html5", "css3", "swift"]:
            logo_color = "black"

        # Format name for URL
        name_encoded = name.replace(" ", "_").replace("-", "--")

        return f'<img src="{base_url}/{name_encoded}-000?style=for-the-badge&logo={icon}&logoColor={logo_color}" alt="{name}" height="25"/>'

    def calculate_user_stats(self, analysis_results):
        """
        Calculates aggregate statistics from all repository analyses.
        """
        total_repos = len(analysis_results)
        total_files = sum(res["total_files"] for res in analysis_results)
        total_lines = sum(res["total_lines"] for res in analysis_results)

        valid_scores = [res["overall_quality_score"] for res in analysis_results if res["overall_quality_score"] > 0]
        avg_quality_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        return {
            "total_repos": total_repos,
            "total_files": total_files,
            "total_lines": total_lines,
            "avg_quality_score": avg_quality_score,
        }

    def fetch_contribution_activity(self):
        """
        Fetches the user's commit activity for the last year.
        """
        from datetime import datetime, timedelta

        today = datetime.utcnow()
        one_year_ago = today - timedelta(days=365)

        activity = defaultdict(int)

        for repo in self.repositories:
            repo_name = repo['name']
            print(f"Fetching commits for {repo_name}...")

            url = f"https://api.github.com/repos/{self.username}/{repo_name}/commits"
            params = {
                "author": self.username,
                "since": one_year_ago.isoformat(),
                "per_page": 100
            }

            page = 1
            while True:
                params["page"] = page
                commits = self._make_github_request(url, params=params)
                if not commits:
                    break

                for commit in commits:
                    try:
                        commit_date_str = commit['commit']['author']['date']
                        commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00')).date()
                        activity[commit_date] += 1
                    except (KeyError, TypeError):
                        continue

                if len(commits) < 100:
                    break
                page += 1

        return activity

    def generate_contribution_svg(self, activity_data):
        """
        Generates an SVG for the contribution graph.
        """
        from datetime import datetime, timedelta

        today = datetime.utcnow().date()
        start_date = today - timedelta(days=364)

        # SVG dimensions
        width = 800
        height = 120
        box_size = 10
        box_margin = 2

        # Colors
        colors = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]

        # Find max contributions for color scaling
        max_contribs = max(activity_data.values()) if activity_data else 1

        svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        svg += f'<style>.day {{ stroke: #1b1f23; stroke-width: 0.1; }}</style>'

        # Month labels
        month_labels = {}

        # Draw squares for each day
        for i in range(365):
            date = start_date + timedelta(days=i)
            week = i // 7
            day_of_week = i % 7

            x = week * (box_size + box_margin)
            y = day_of_week * (box_size + box_margin)

            contribs = activity_data.get(date, 0)

            if contribs == 0:
                color_index = 0
            elif contribs == 1:
                color_index = 1
            elif contribs <= max_contribs * 0.4:
                color_index = 2
            elif contribs <= max_contribs * 0.7:
                color_index = 3
            else:
                color_index = 4

            color = colors[color_index]

            svg += f'<rect x="{x}" y="{y}" width="{box_size}" height="{box_size}" fill="{color}" class="day" />'

            # Store month labels
            if date.day == 1:
                month_labels[week] = date.strftime("%b")

        # Add month labels to SVG
        for week, month in month_labels.items():
            x = week * (box_size + box_margin)
            svg += f'<text x="{x}" y="{height - 5}" font-size="10" fill="#777">{month}</text>'

        svg += '</svg>'
        return svg

    def generate_contribution_activity_md(self):
        """
        Generates the local contribution activity graph.
        """
        print("Fetching contribution activity...")
        activity_data = self.fetch_contribution_activity()

        print("Generating contribution SVG...")
        svg_content = self.generate_contribution_svg(activity_data)

        # Save SVG to file
        with open("contribution_graph.svg", "w") as f:
            f.write(svg_content)

        return f"""## Contribution Activity
<div align="center">
  <img src="contribution_graph.svg" alt="Contribution Graph" />
</div>
"""

    def format_user_stats_markdown(self, user_stats):
        """
        Formats the user statistics into a Markdown table.
        """
        markdown = "### 📊 My GitHub Stats\n\n"
        markdown += "| Stat                  | Value         |\n"
        markdown += "|-----------------------|---------------|\n"
        markdown += f"| Repositories Analyzed | {user_stats['total_repos']} |\n"
        markdown += f"| Total Files           | {user_stats['total_files']:,} |\n"
        markdown += f"| Total Lines of Code   | {user_stats['total_lines']:,} |\n"
        markdown += f"| Avg. Code Quality     | {user_stats['avg_quality_score']:.2f}% |\n\n"
        return markdown

    def analyze_all_repositories(self):
        """
        Orchestrates the analysis of all user repositories.
        """
        if not self.repositories:
            self.fetch_user_repositories()

        analysis_results = []
        for repo in self.repositories:
            repo_name = repo['name']

            # Check if repository is accessible before analysis
            if not self._is_repository_accessible(repo_name):
                print(f"Skipping {repo_name} as it is private or inaccessible.")
                continue

            # Analyze structure first
            structure_analysis = self.analyze_repository_structure(repo_name)

            # Fetch languages, passing in the analysis result
            languages = self.fetch_repository_languages(repo_name, structure_analysis)
            if not languages:
                print(f"Skipping {repo_name} as it has no detectable languages or is empty.")
                continue

            # Combine results
            combined_analysis = {
                "repo_name": repo_name,
                "languages": languages,
                **structure_analysis
            }
            analysis_results.append(combined_analysis)

        return analysis_results

    def calculate_percentages(self, analysis_results):
        """
        Calculates the percentage of each language across all repositories.
        """
        total_bytes = defaultdict(int)
        for result in analysis_results:
            for lang, byte_count in result.get("languages", {}).items():
                total_bytes[lang] += byte_count

        total = sum(total_bytes.values())
        if not total:
            return {}

        return {lang: (count / total) * 100 for lang, count in total_bytes.items()}

    def calculate_language_proficiency(self, analysis_results):
        """
        Calculates proficiency score based on quantitative metrics.
        """
        lang_metrics = defaultdict(lambda: {
            'total_lines': 0,
            'total_commits': 0,
            'repositories': set(),
        })

        # Collect metrics for each language
        for result in analysis_results:
            repo_name = result.get("repo_name", "")
            if not repo_name:
                continue

            commit_data = self._get_repository_commits(repo_name)

            for lang, lines in result.get("languages", {}).items():
                if lines > 0:
                    metrics = lang_metrics[lang]
                    metrics['total_lines'] += lines
                    metrics['repositories'].add(repo_name)
                    metrics['total_commits'] += self._analyze_language_commits(commit_data, lang)

        # Calculate final proficiency scores
        proficiency = {}
        # New simplified weights (can be moved to config)
        commits_weight = 0.4
        lines_weight = 0.3
        repo_weight = 0.3

        min_commits = self.config.get("github", {}).get("min_commits_for_proficiency", 5)
        min_lines = self.config.get("github", {}).get("min_lines_for_proficiency", 100)

        for lang, metrics in lang_metrics.items():
            if metrics['total_commits'] < min_commits or metrics['total_lines'] < min_lines:
                continue

            # Normalize metrics (0-100 scale)
            commit_score = min(100, (metrics['total_commits'] / 50) * 100)  # 50+ commits = 100
            lines_score = min(100, (metrics['total_lines'] / 10000) * 100)  # 10k+ lines = 100
            repo_score = min(100, (len(metrics['repositories']) / 10) * 100)  # 10+ repos = 100

            # Combined proficiency score
            final_score = (
                commit_score * commits_weight +
                lines_score * lines_weight +
                repo_score * repo_weight
            )

            proficiency[lang] = min(100, final_score)

        return proficiency

    def _get_repository_commits(self, repo_name):
        """
        Fetches commit data for a repository to analyze contribution patterns.
        """
        # Validate repository name
        if not repo_name or not repo_name.strip():
            print(f"Warning: Invalid repository name (empty or None)")
            return []

        repo_name = repo_name.strip()

        try:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}/commits"
            params = {"author": self.username, "per_page": 100}
            response = self._make_github_request(url, params)
            if response is None:
                print(f"Warning: Repository {repo_name} may be private or inaccessible")
                return []
            return response
        except Exception as e:
            print(f"Warning: Could not fetch commits for {repo_name}: {e}")
            return []

    def _analyze_language_commits(self, commits, language):
        """
        Analyzes commits to estimate language-specific contributions.
        """
        if not commits:
            return 0

        # Simple heuristic: assume commits are distributed by language usage
        # In a real implementation, you might analyze diff data
        return len(commits)

    def _get_language_code_samples(self, repo_analysis, language):
        """
        Extracts code samples for a specific language from repository analysis.
        """
        samples = []
        for file_info in repo_analysis.get("analyzed_files", []):
            if self._detect_file_language(file_info.get("path", "")) == language:
                content = file_info.get("content", "")
                if len(content) > 100:  # Substantial code samples
                    samples.append(content[:1000])  # First 1KB
                if len(samples) >= 3:  # Max 3 samples per language per repo
                    break
        return samples



    def get_proficiency_level_description(self, score):
        """
        Returns a descriptive level based on a proficiency score using config levels.
        """
        levels = self.config.get("proficiency", {}).get("levels", [
            "🔰 Novice", "📚 Learning", "⚡ Developing", "💪 Competent",
            "🎯 Proficient", "🚀 Advanced", "⭐ Expert", "🏆 Master"
        ])

        # Map score (0-100) to level index
        level_index = min(len(levels) - 1, int(score / (100 / len(levels))))
        return levels[level_index]

    def generate_ranking(self, percentages, proficiency):
        """
        Generates a ranked list of languages based on usage and proficiency.
        """
        if not percentages:
            return []

        combined_scores = {}
        for lang, pct in percentages.items():
            prof_score = proficiency.get(lang, 0)
            # Weighted score: 60% usage, 40% proficiency
            combined_scores[lang] = (pct * 0.6) + (prof_score * 0.4)

        sorted_languages = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

        ranking = []
        for i, (lang, score) in enumerate(sorted_languages[:7]): # Top 7
            level = self.get_proficiency_level_description(proficiency.get(lang, 0))
            ranking.append({
                "rank": i + 1,
                "language": lang,
                "percentage": percentages.get(lang, 0),
                "level": level
            })
        return ranking

    def get_random_citation(self):
        """
        Returns a random citation or quote.
        """
        citations = [
            "Talk is cheap. Show me the code. - Linus Torvalds",
            "Programs must be written for people to read, and only incidentally for machines to execute. - Abelson & Sussman",
            "Any fool can write code that a computer can understand. Good programmers write code that humans can understand. - Martin Fowler",
            "The best way to predict the future is to invent it. - Alan Kay",
            "Measuring programming progress by lines of code is like measuring aircraft building progress by weight. - Bill Gates"
        ]
        return random.choice(citations)

    def get_current_timestamp(self):
        """
        Returns the current timestamp in a specific timezone.
        """
        return datetime.now(pytz.timezone("UTC")).strftime("%Y-%m-%d %H:%M:%S %Z")

    def generate_profile_readme(self, ranking, user_stats, tech_stack_md, contribution_activity_md):
        """
        Generates the new, streamlined README.md.
        """
        readme = f"""<div align="center">
# 👋 Hi, I'm {self.username}!
*A passionate developer focused on creating elegant and effective solutions.*
</div>

---

{self.generate_coding_proficiency_analysis_md(ranking, user_stats)}

---

{tech_stack_md}

---

{contribution_activity_md}

---

<div align="center">
<p>Last updated: {self.get_current_timestamp()}</p>
</div>
"""
        return readme

    def generate_coding_proficiency_analysis_md(self, ranking, user_stats):
        """
        Generates the redesigned 'Coding Proficiency Analysis' section.
        """
        if not ranking:
            return "## Coding Proficiency Analysis\n\n*No language data available to display.*\n"

        # Main stats
        stats_md = f"""| Stat | Value |
|---|---|
| **Repositories Analyzed** | {user_stats.get('total_repos', 0)} |
| **Total Lines of Code** | {user_stats.get('total_lines', 0):,} |
| **Avg. Code Quality** | {user_stats.get('avg_quality_score', 0):.1f}% |
"""

        # Language ranking
        ranking_md = """| Rank | Language | Usage | Proficiency |
|---|---|---|---|
"""
        for i, item in enumerate(ranking[:5]): # Top 5
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            progress_bar = self._create_progress_bar(item['percentage'])
            ranking_md += f"| {rank_emoji} | **{item['language']}** | `{progress_bar}` {item['percentage']:.1f}% | *{item['level']}* |\n"


        return f"""## Coding Proficiency Analysis\n\n<table>\n<tr>\n<td width=\"40%\" valign=\"top">\n\n{stats_md}\n\n</td>\n<td width=\"60%\" valign=\"top">\n\n{ranking_md}\n\n</td>\n</tr>\n</table>\n\n<details>\n<summary>How is proficiency calculated?</summary>\nProficiency is a weighted score based on commit frequency, volume of code, and the number of repositories a language is used in. It does not use AI analysis.\n</details>\n"""

    def _create_progress_bar(self, percentage, length=10):
        """
        Creates a visual progress bar for percentages.
        """
        filled = int((percentage / 100) * length)
        empty = length - filled
        return f"{'█' * filled}{'░' * empty}"

    def _get_quality_distribution(self, avg_quality, quality_type):
        """
        Returns mock quality distribution percentages.
        """
        if quality_type == 'high':
            return min(90, max(10, int(avg_quality)))
        elif quality_type == 'good':
            return min(40, max(10, int(100 - avg_quality)))
        else:
            return max(0, min(30, int(100 - avg_quality * 1.3)))

    def _calculate_years_active(self):
        """
        Estimates years active based on current date.
        """
        from datetime import datetime
        return max(1, datetime.now().year - 2020)  # Assume started in 2020

    def _get_language_color(self, language):
        """
        Returns appropriate color codes for language badges.
        """
        color_map = {
            'python': '3776ab',
            'javascript': 'f7df1e',
            'typescript': '3178c6',
            'java': 'ed8b00',
            'cpp': '00599c',
            'c': '555555',
            'go': '00add8',
            'rust': '000000',
            'php': '777bb4',
            'ruby': 'cc342d',
            'swift': 'fa7343',
            'kotlin': '7f52ff',
            'scala': 'dc322f',
            'html': 'e34f26',
            'css': '1572b6'
        }
        return color_map.get(language.lower(), '6e7781')

    def _get_language_logo(self, language):
        """
        Returns appropriate logo names for language badges.
        """
        logo_map = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'java': 'java',
            'cpp': 'cplusplus',
            'c': 'c',
            'go': 'go',
            'rust': 'rust',
            'php': 'php',
            'ruby': 'ruby',
            'swift': 'swift',
            'kotlin': 'kotlin',
            'scala': 'scala',
            'html': 'html5',
            'css': 'css3'
        }
        return logo_map.get(language.lower(), 'code')

    def format_ranking_markdown(self, ranking):
        """
        Legacy method - kept for compatibility.
        """
        return self._create_ranking_card(ranking)

def main():
    """
    Main function to run the script.
    """
    start_time = time.time()

    # Use config to get username, or fallback
    try:
        with open("config.toml", "rb") as f:
            config = tomli.load(f)
        username = config.get("github", {}).get("username")
        if not username:
            raise ValueError("GitHub username not found in config.toml")
    except (FileNotFoundError, ValueError, tomli.TOMLDecodeError) as e:
        print(f"Error loading configuration: {e}")
        print("Please ensure 'config.toml' exists and contains a [github] section with a 'username' key.")
        return

    try:
        analyzer = GitHubLanguageAnalyzer(username=username, use_simulation=False)

        # 1. Analyze all repositories
        analysis_results = analyzer.analyze_all_repositories()

        if not analysis_results:
            print("No repositories were analyzed. Exiting.")
            return

        # 2. Calculate overall stats
        user_stats = analyzer.calculate_user_stats(analysis_results)

        # 3. Calculate language percentages and proficiency
        percentages = analyzer.calculate_percentages(analysis_results)
        user_stats['total_languages'] = len(percentages)
        proficiency = analyzer.calculate_language_proficiency(analysis_results)

        # 4. Generate language ranking
        ranking = analyzer.generate_ranking(percentages, proficiency)

        # 5. Generate Project Showcase
        project_showcase_md = analyzer.generate_project_showcase_md(analysis_results)

        # 6. Generate contribution activity graph
        contribution_activity_md = analyzer.generate_contribution_activity_md()

        # 7. Generate the full README content
        readme_content = analyzer.generate_profile_readme(ranking, user_stats, project_showcase_md, contribution_activity_md)

        # 8. Write to file and save cache
        with open("PROFILE_README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        analyzer.save_ai_cache()

        print("\n✅ Successfully generated PROFILE_README.md")
        print(f"Total execution time: {time.time() - start_time:.2f} seconds")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
