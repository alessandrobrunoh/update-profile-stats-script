import os
import sys
import subprocess
import time
import base64
import random
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
import google.generativeai as genai

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

        if not self.github_token:
            print("Warning: GITHUB_TOKEN environment variable not set. API requests may be rate-limited.")

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set. It's required for code analysis.")

        # Configure the Gemini client
        genai.configure(api_key=self.gemini_api_key)  # type: ignore
        gemini_model_name = self.config.get("gemini", {}).get("model", "gemini-1.5-flash")
        self.gemini_model = genai.GenerativeModel(gemini_model_name)  # type: ignore

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

        print(f"Fetching repositories for user: {self.username}")
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/users/{self.username}/repos"
            params = {"per_page": 100, "page": page}
            page_repos = self._make_github_request(url, params=params)
            if not page_repos:
                break
            repos.extend(page_repos)
            if len(page_repos) < 100:
                break
            page += 1

        exclude_repos = self.config.get("github", {}).get("exclude_repos", [])
        self.repositories = [repo for repo in repos if not repo['fork'] and repo['name'] not in exclude_repos]
        print(f"Found {len(self.repositories)} non-forked repositories.")
        return self.repositories

    def fetch_repository_languages(self, repo_name):
        """
        Fetches language data for a specific repository with generated code filtering.
        """
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        raw_languages = self._make_github_request(url) or {}

        # Filter out excluded languages
        excluded_languages = set(self.config.get("github", {}).get("exclude_languages", []))
        filtered_languages = {
            lang: bytes_count for lang, bytes_count in raw_languages.items()
            if lang not in excluded_languages
        }

        # If enabled, check for generated code and adjust language stats
        if self.config.get("github", {}).get("exclude_generated_code", True):
            filtered_languages = self._filter_generated_code_languages(repo_name, filtered_languages)

        return filtered_languages

    def _filter_generated_code_languages(self, repo_name, languages):
        """
        Analyzes repository structure and filters out generated code from language stats.
        """
        try:
            # Get repository structure
            repo_structure = self.analyze_repository_structure(repo_name)
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

        # Use AI to detect generated code patterns
        if len(content) > 100:  # Only for substantial files
            return self._ai_detect_generated_code(content[:2000])  # First 2KB

        return False

    def _ai_detect_generated_code(self, code_content):
        """
        Uses AI to detect if code appears to be auto-generated.
        """
        try:
            prompt = self.config.get("gemini", {}).get("generated_code_prompt", "")
            if not prompt:
                return False

            full_prompt = f"{prompt}\n\nCode:\n{code_content}"
            response = self.gemini_model.generate_content(full_prompt)
            result = response.text.strip().upper()
            return "GENERATED" in result
        except Exception as e:
            print(f"Warning: AI generated code detection failed: {e}")
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

    def _get_gemini_code_quality_score(self, code_content):
        """
        Analyzes code content using the Gemini API and returns a quality score.
        """
        if not code_content or code_content.isspace():
            return 0

        prompt_template = self.config.get("gemini", {}).get("prompt", "Analyze this code and give a quality score from 0 to 100.")
        full_prompt = f"{prompt_template}\n\n--- CODE ---\n{code_content}"

        try:
            response = self.gemini_model.generate_content(full_prompt)
            # Extract the score, assuming the API returns just the number as requested.
            score_text = ''.join(filter(str.isdigit, response.text))
            if not score_text:
                return 0
            score = int(score_text)
            return max(0, min(100, score)) # Clamp score between 0 and 100
        except Exception as e:
            print(f"An error occurred while calling Gemini API: {e}")
            return 0 # Return a default score on error

    def analyze_repository_structure(self, repo_name):
        """
        Analyzes a repository's structure, files, and estimates code quality using Gemini.
        """
        print(f"Analyzing repository structure for: {repo_name}")
        if self.use_simulation:
            return self._simulate_repository_analysis(repo_name)

        contents = self._get_repository_contents(repo_name)
        if not contents:
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

                    # Use Gemini for quality score
                    quality_score = self._get_gemini_code_quality_score(file_content)
                    quality_scores.append(quality_score)
                    time.sleep(1) # Add a small delay to avoid hitting API rate limits

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
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/git/trees/main?recursive=1"
        data = self._make_github_request(url)
        if not data or 'tree' not in data:
            return []

        exclude_dirs = self.config.get("exclusions", {}).get("exclude_dirs", [])

        # Filter out excluded directories at the beginning
        filtered_tree = [
            item for item in data['tree']
            if not any(excluded_dir in item['path'] for excluded_dir in exclude_dirs)
        ]
        return filtered_tree

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

    def generate_tech_stack_markdown(self, detected_tech):
        """
        Generates beautiful categorized Markdown for the detected technology stack.
        """
        if not detected_tech:
            return ""

        # Categorize technologies
        categories = {
            "🎨 Frontend": ["react", "vue", "angular", "next.js", "nuxt.js", "gatsby", "svelte", "tailwind"],
            "⚙️ Backend": ["django", "flask", "spring", "express", "laravel", "rubyonrails", "fastapi"],
            "☁️ Cloud & DevOps": ["docker", "kubernetes", "terraform", "ansible", "aws", "azure", "gcp"],
            "🧪 Testing": ["jest", "pytest", "junit", "mocha", "cypress", "selenium"],
            "🔧 Build Tools": ["webpack", "babel", "vite", "gulp", "grunt"],
            "💾 Database": ["mongodb", "postgresql", "mysql", "redis", "elasticsearch"],
            "🛠️ Tools": ["git", "github", "vscode", "intellij", "npm", "yarn"]
        }

        markdown = """## 🚀 Technology Stack

<div align="center">

### 🛠️ What I Work With

</div>

"""

        # Generate categorized sections
        for category, tech_keys in categories.items():
            category_techs = [tech for tech in detected_tech if tech in tech_keys]
            if category_techs:
                markdown += f"**{category}**\n\n<div align=\"center\">\n\n"

                for tech_key in sorted(category_techs):
                    if tech_key in self.tech_stack_mapping:
                        display_name, icon_name = self.tech_stack_mapping[tech_key]
                        badge = self._format_tech_badge(display_name, icon_name)
                        markdown += f"{badge}\n"

                markdown += "\n</div>\n\n"

        # Add uncategorized technologies
        uncategorized = []
        all_categorized = [tech for techs in categories.values() for tech in techs]
        for tech in detected_tech:
            if tech not in all_categorized and tech in self.tech_stack_mapping:
                uncategorized.append(tech)

        if uncategorized:
            markdown += "**🔧 Other Technologies**\n\n<div align=\"center\">\n\n"
            for tech_key in sorted(uncategorized):
                display_name, icon_name = self.tech_stack_mapping[tech_key]
                badge = self._format_tech_badge(display_name, icon_name)
                markdown += f"{badge}\n"
            markdown += "\n</div>\n\n"

        markdown += """---

<div align="center">
  <img src="https://skillicons.dev/icons?i=""" + ",".join([self.tech_stack_mapping[tech][1] for tech in list(detected_tech)[:15] if tech in self.tech_stack_mapping]) + """" />
</div>

"""

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

            # Fetch languages first to get a sense of the repo
            languages = self.fetch_repository_languages(repo_name)
            if not languages:
                print(f"Skipping {repo_name} as it has no detectable languages or is empty.")
                continue

            # Analyze structure and quality
            structure_analysis = self.analyze_repository_structure(repo_name)

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
        Calculates enhanced proficiency score for each language based on multiple factors.
        """
        lang_metrics = defaultdict(lambda: {
            'total_lines': 0,
            'total_commits': 0,
            'repositories': set(),
            'quality_scores': [],
            'complexity_scores': [],
            'ai_proficiency_scores': []
        })

        # Collect metrics for each language
        for result in analysis_results:
            repo_name = result.get("repository", "")

            # Get commit data for this repository
            commit_data = self._get_repository_commits(repo_name)

            for lang, lines in result.get("languages", {}).items():
                if lines > 0:
                    metrics = lang_metrics[lang]

                    # Lines of code
                    metrics['total_lines'] += lines

                    # Repository count
                    metrics['repositories'].add(repo_name)

                    # Quality scores
                    quality = result.get("overall_quality_score", 0)
                    if quality > 0:
                        metrics['quality_scores'].append(quality)

                    # Commit analysis for this language in this repo
                    lang_commits = self._analyze_language_commits(commit_data, lang)
                    metrics['total_commits'] += lang_commits

                    # AI-powered proficiency assessment
                    code_samples = self._get_language_code_samples(result, lang)
                    if code_samples:
                        ai_score = self._ai_assess_language_proficiency(code_samples, lang)
                        if ai_score > 0:
                            metrics['ai_proficiency_scores'].append(ai_score)

        # Calculate final proficiency scores
        proficiency = {}
        config_weights = self.config.get("proficiency", {})

        commits_weight = config_weights.get("commits_weight", 0.3)
        lines_weight = config_weights.get("lines_of_code_weight", 0.25)
        quality_weight = config_weights.get("code_quality_weight", 0.25)
        repo_weight = config_weights.get("repository_count_weight", 0.1)
        complexity_weight = config_weights.get("complexity_weight", 0.1)

        min_commits = self.config.get("github", {}).get("min_commits_for_proficiency", 5)
        min_lines = self.config.get("github", {}).get("min_lines_for_proficiency", 100)

        for lang, metrics in lang_metrics.items():
            # Skip languages with insufficient activity
            if metrics['total_commits'] < min_commits or metrics['total_lines'] < min_lines:
                continue

            # Normalize metrics (0-100 scale)
            commit_score = min(100, (metrics['total_commits'] / 50) * 100)  # 50+ commits = 100
            lines_score = min(100, (metrics['total_lines'] / 10000) * 100)  # 10k+ lines = 100
            repo_score = min(100, (len(metrics['repositories']) / 10) * 100)  # 10+ repos = 100

            # Average quality and AI scores
            avg_quality = sum(metrics['quality_scores']) / len(metrics['quality_scores']) if metrics['quality_scores'] else 50
            avg_ai_score = sum(metrics['ai_proficiency_scores']) / len(metrics['ai_proficiency_scores']) if metrics['ai_proficiency_scores'] else 50

            # Combined proficiency score
            final_score = (
                commit_score * commits_weight +
                lines_score * lines_weight +
                avg_quality * quality_weight +
                repo_score * repo_weight +
                avg_ai_score * complexity_weight
            )

            proficiency[lang] = min(100, final_score)

        return proficiency

    def _get_repository_commits(self, repo_name):
        """
        Fetches commit data for a repository to analyze contribution patterns.
        """
        try:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}/commits"
            params = {"author": self.username, "per_page": 100}
            return self._make_github_request(url, params) or []
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

    def _ai_assess_language_proficiency(self, code_samples, language):
        """
        Uses AI to assess proficiency level based on code samples.
        """
        try:
            if not code_samples:
                return 0

            prompt_template = self.config.get("gemini", {}).get("proficiency_prompt", "")
            if not prompt_template:
                return 0

            # Combine samples for analysis
            combined_code = "\n\n--- Sample ---\n\n".join(code_samples)
            full_prompt = prompt_template.format(language=language) + f"\n\nCode samples:\n{combined_code}"

            response = self.gemini_model.generate_content(full_prompt)
            result = response.text.strip()

            # Extract numeric score (1-10)
            import re
            score_match = re.search(r'\b([1-9]|10)\b', result)
            if score_match:
                score = int(score_match.group(1))
                return score * 10  # Convert to 0-100 scale

            return 0
        except Exception as e:
            print(f"Warning: AI proficiency assessment failed for {language}: {e}")
            return 0

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

    def generate_profile_readme(self, ranking, user_stats, tech_stack_md):
        """
        Generates a beautiful, comprehensive README.md with enhanced visuals.
        """
        config = self.config.get("output", {})
        use_emoji = config.get("use_emoji", True)
        use_badges = config.get("use_badges", True)

        # Header with animated typing effect
        readme = f"""<div align="center">

# {f"👋 Hi, I'm {self.username}!" if use_emoji else f"Hi, I'm {self.username}!"}

<img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=22&pause=1000&color=2E9EF7&center=true&vCenter=true&width=440&lines=Welcome+to+my+GitHub+profile!;Passionate+Developer+%26+Problem+Solver;Always+learning+new+technologies" alt="Typing SVG" />

![Profile Views](https://komarev.com/ghpvc/?username={self.username}&color=blue&style=flat-square)
[![GitHub followers](https://img.shields.io/github/followers/{self.username}?style=social)](https://github.com/{self.username})

</div>

---

## 📊 GitHub Analytics

<div align="center">
  <img height="180em" src="https://github-readme-stats.vercel.app/api?username={self.username}&show_icons=true&theme=tokyonight&include_all_commits=true&count_private=true"/>
  <img height="180em" src="https://github-readme-stats.vercel.app/api/top-langs/?username={self.username}&layout=compact&langs_count=8&theme=tokyonight"/>
</div>

<div align="center">
  <img src="https://github-readme-streak-stats.herokuapp.com/?user={self.username}&theme=tokyonight" alt="GitHub Streak"/>
</div>

---

"""

        # Enhanced stats and ranking in beautiful cards
        readme += """<div align="center">

## 🎯 Coding Proficiency Analysis

<table>
<tr>
<td width="50%" valign="top">

"""
        readme += self._create_stats_card(user_stats)
        readme += """

</td>
<td width="50%" valign="top">

"""
        readme += self._create_ranking_card(ranking)
        readme += """

</td>
</tr>
</table>

</div>

---

"""

        # Enhanced tech stack
        readme += tech_stack_md

        # Activity graph
        readme += f"""---

## 📈 Contribution Activity

<div align="center">
  <img src="https://github-readme-activity-graph.vercel.app/graph?username={self.username}&theme=tokyo-night&bg_color=1a1b27&color=5aa2f7&line=f7df1e&point=ffffff&area=true&hide_border=true" width="100%"/>
</div>

---

## 🏆 GitHub Achievements

<div align="center">
  <img src="https://github-profile-trophy.vercel.app/?username={self.username}&theme=tokyonight&no-frame=true&no-bg=true&margin-w=4&row=1" width="100%"/>
</div>

---

## 💡 Random Dev Quote

<div align="center">
  <img src="https://quotes-github-readme.vercel.app/api?type=horizontal&theme=tokyonight" />
</div>

---

## 🌟 What I'm Up To

- 🔭 Currently working on innovative projects
- 🌱 Always learning and exploring new technologies
- 👯 Open to collaborating on exciting projects
- 💬 Ask me about anything tech-related
- ⚡ Fun fact: Code is poetry in motion!

---

<div align="center">

### 📫 Let's Connect!

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/{self.username})
[![Twitter](https://img.shields.io/badge/Twitter-1DA1F2?style=for-the-badge&logo=twitter&logoColor=white)](https://twitter.com/{self.username})
[![Portfolio](https://img.shields.io/badge/Portfolio-FF5722?style=for-the-badge&logo=google-chrome&logoColor=white)](https://{self.username}.dev)

---

*{self.get_random_citation()}*

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=100&section=footer"/>

<p align="center">
  <img src="https://img.shields.io/badge/Made%20with-❤️-red.svg"/>
  <img src="https://img.shields.io/badge/Last%20Updated-{self.get_current_timestamp().replace(' ', '%20').replace(':', '%3A')}-blue.svg"/>
</p>

</div>

"""

        return readme

    def _create_stats_card(self, user_stats):
        """
        Creates a beautiful stats card with key metrics.
        """
        if not user_stats:
            return "### 📊 Repository Stats\n\n*No stats available*"

        total_repos = user_stats.get('total_repositories', 0)
        total_languages = user_stats.get('total_languages', 0)
        avg_quality = user_stats.get('average_quality_score', 0)

        markdown = f"""### 📊 Repository Statistics

<div align="center">

| 🎯 Metric | 📈 Value |
|-----------|----------|
| **🗂️ Total Repositories** | `{total_repos}` |
| **🔤 Languages Mastered** | `{total_languages}` |
| **⭐ Avg Code Quality** | `{avg_quality:.1f}/100` |
| **🚀 Years Active** | `{self._calculate_years_active()}+` |

</div>

**🎨 Quality Distribution:**
```
High Quality (80-100): ████████░░ {self._get_quality_distribution(avg_quality, 'high')}%
Good Quality (60-79):  ██████░░░░ {self._get_quality_distribution(avg_quality, 'good')}%
Needs Work (<60):      ████░░░░░░ {self._get_quality_distribution(avg_quality, 'low')}%
```"""

        return markdown

    def _create_ranking_card(self, ranking):
        """
        Creates a beautiful ranking card with language proficiency.
        """
        if not ranking:
            return "### 🏆 Language Proficiency\n\n*No language data available*"

        markdown = """### 🏆 Language Proficiency

<div align="center">

| 🥇 Rank | 💻 Language | 📊 Usage | 🎯 Proficiency |
|---------|-------------|----------|----------------|"""

        for i, item in enumerate(ranking[:8]):  # Top 8 languages
            rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{item['rank']}"
            progress_bar = self._create_progress_bar(item['percentage'])
            markdown += f"\n| {rank_emoji} | **{item['language']}** | {progress_bar} {item['percentage']:.1f}% | {item['level']} |"

        markdown += "\n\n</div>\n\n"

        # Add language badges
        markdown += "**🚀 Tech Arsenal:**\n\n<div align=\"center\">\n\n"
        for item in ranking[:6]:
            lang = item['language'].lower()
            color = self._get_language_color(lang)
            markdown += f"![{item['language']}](https://img.shields.io/badge/{item['language'].replace(' ', '%20')}-{item['percentage']:.1f}%25-{color}?style=flat-square&logo={self._get_language_logo(lang)}&logoColor=white)\n"

        markdown += "\n</div>"

        return markdown

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
        proficiency = analyzer.calculate_language_proficiency(analysis_results)

        # 4. Generate language ranking
        ranking = analyzer.generate_ranking(percentages, proficiency)

        # 5. Detect tech stack
        detected_tech = analyzer.detect_frameworks_from_repos(analysis_results)
        tech_stack_md = analyzer.generate_tech_stack_markdown(detected_tech)

        # 6. Generate the full README content
        readme_content = analyzer.generate_profile_readme(ranking, user_stats, tech_stack_md)

        # 7. Write to file
        with open("PROFILE_README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        print("\n✅ Successfully generated PROFILE_README.md")
        print(f"Total execution time: {time.time() - start_time:.2f} seconds")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
