import os
import sys
import subprocess
import time
import base64
import random
import json
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

# Import dependencies after ensuring they're available
try:
    import pytz
    import requests
    import tomli
    from dotenv import load_dotenv

    # Load environment variables from .env file at the start
    load_dotenv()
except ImportError as e:
    print(f"❌ Failed to import required dependency: {e}")
    print("Please ensure all dependencies are properly installed")
    sys.exit(1)

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
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                gemini_model_name = self.config.get("gemini", {}).get("model", "gemini-1.5-flash")
                self.gemini_model = genai.GenerativeModel(gemini_model_name)
            except ImportError:
                print("❌ google.generativeai not available. AI features disabled.")
                self.gemini_model = None

    def load_ai_cache(self):
        """Load AI analysis cache to avoid redundant API calls."""
        try:
            if os.path.exists("ai_cache.json"):
                with open("ai_cache.json", "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_ai_cache(self):
        """Save AI analysis cache for future use."""
        try:
            with open("ai_cache.json", "w") as f:
                json.dump(self.ai_cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save AI cache: {e}")

    def load_config(self, config_path):
        """Load configuration from TOML file."""
        try:
            with open(config_path, "rb") as f:
                return tomli.load(f)
        except FileNotFoundError:
            print(f"Configuration file '{config_path}' not found. Using defaults.")
            return {}
        except Exception as e:
            print(f"Error loading configuration: {e}. Using defaults.")
            return {}

    def _extract_username_from_repo(self):
        """Extract username from GITHUB_REPOSITORY environment variable."""
        repo = os.getenv("GITHUB_REPOSITORY")
        if repo and "/" in repo:
            return repo.split("/")[0]
        return None

    def _make_github_request(self, url, params=None):
        """Makes a request to the GitHub API with error handling."""
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"Rate limit exceeded or access denied for {url}")
                return None
            elif response.status_code == 404:
                print(f"Resource not found: {url}")
                return None
            else:
                print(f"GitHub API request failed: {response.status_code} for {url}")
                return None
        except Exception as e:
            print(f"Error making GitHub API request: {e}")
            return None

    def fetch_user_repositories(self):
        """Fetches all repositories for a given user."""
        repos = []
        page = 1
        per_page = 100

        while True:
            url = f"https://api.github.com/users/{self.username}/repos"
            params = {
                "type": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
                "page": page
            }

            data = self._make_github_request(url, params)
            if not data:
                break

            repos.extend(data)
            if len(data) < per_page:
                break
            page += 1

        return repos

    def fetch_repository_languages(self, repo_name):
        """Fetch languages for a specific repository."""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        return self._make_github_request(url) or {}

    def _filter_generated_code_languages(self, languages):
        """
        Filters out languages that are likely generated code based on configuration.
        """
        exclude_languages = self.config.get("github", {}).get("exclude_languages", [])
        filtered = {}

        for lang, lines in languages.items():
            if lang not in exclude_languages:
                filtered[lang] = lines

        return filtered

    def _is_generated_file(self, file_path, content_sample=""):
        """
        Enhanced detection of generated files using configuration patterns.
        """
        # Check against exclude patterns from config
        exclude_files = self.config.get("exclusions", {}).get("exclude_files", [])
        framework_generated = self.config.get("exclusions", {}).get("framework_generated_files", [])
        generated_patterns = self.config.get("exclusions", {}).get("generated_code_patterns", [])

        # Check file name patterns
        for pattern in exclude_files + framework_generated:
            if self._matches_pattern(file_path, pattern):
                return True

        # Check content patterns
        content_lower = content_sample.lower()
        for pattern in generated_patterns:
            if pattern.lower() in content_lower:
                return True

        return False

    def _detect_file_language(self, file_path):
        """
        Simple file extension to language mapping.
        """
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".java": "Java", ".cpp": "C++", ".c": "C", ".cs": "C#",
            ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
            ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala",
            ".html": "HTML", ".css": "CSS", ".scss": "SCSS"
        }

        for ext, lang in ext_map.items():
            if file_path.lower().endswith(ext):
                return lang
        return None

    def _matches_pattern(self, file_path, pattern):
        """Check if file path matches a glob-like pattern."""
        import fnmatch
        return fnmatch.fnmatch(file_path.lower(), pattern.lower())

    def _is_repository_accessible(self, repo_name):
        """Check if we can access the repository."""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}"
        response = self._make_github_request(url)
        return response is not None

    def analyze_repository_structure(self, repo_name):
        """
        Enhanced repository analysis with better generated code detection.
        """
        if not self._is_repository_accessible(repo_name):
            print(f"⚠️ Repository {repo_name} is not accessible")
            return self._get_fallback_repo_data(repo_name)

        try:
            # Get basic language data from GitHub API
            languages = self.fetch_repository_languages(repo_name)
            if not languages:
                return self._get_fallback_repo_data(repo_name)

            # Filter out excluded languages
            filtered_languages = self._filter_generated_code_languages(languages)

            # Get repository contents for deeper analysis
            repo_contents = self._get_repository_contents(repo_name)

            # AI-based analysis if available
            ai_summary = ""
            if self.gemini_model and repo_contents:
                ai_summary = self._ai_summarize_repository(repo_name, repo_contents, filtered_languages)

            result = {
                "repo_name": repo_name,
                "languages": filtered_languages,
                "total_lines": sum(filtered_languages.values()),
                "primary_language": max(filtered_languages.items(), key=lambda x: x[1])[0] if filtered_languages else "Unknown",
                "ai_summary": ai_summary,
                "analysis_timestamp": datetime.now().isoformat()
            }

            return result

        except Exception as e:
            print(f"Error analyzing {repo_name}: {e}")
            return self._get_fallback_repo_data(repo_name)

    def _get_repository_contents(self, repo_name, path="", max_files=50):
        """Get repository contents for analysis."""
        try:
            return self._fetch_repo_contents_from_api(repo_name, path, max_files)
        except Exception as e:
            print(f"Error fetching contents for {repo_name}: {e}")
            return []

    def _fetch_repo_contents_from_api(self, repo_name, path="", max_files=50):
        """Fetch repository contents from GitHub API."""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{path}"
        data = self._make_github_request(url)

        if not data:
            return []

        contents = []
        file_count = 0

        for item in data:
            if file_count >= max_files:
                break

            if item["type"] == "file" and not self._should_exclude_file(item["name"]):
                file_content = self._get_file_content(item["download_url"])
                if file_content:
                    contents.append({
                        "name": item["name"],
                        "path": item["path"],
                        "content": file_content[:2000],  # Limit content size
                        "language": self._detect_file_language(item["name"])
                    })
                    file_count += 1

        return contents

    def _get_latest_commit_sha(self, repo_name):
        """Get the latest commit SHA for a repository."""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/commits"
        commits = self._make_github_request(url)
        return commits[0]["sha"] if commits else None

    def _get_file_content(self, download_url):
        """Get file content from download URL."""
        try:
            response = requests.get(download_url, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return ""

    def _simulate_repository_analysis(self, repo_name):
        """
        Simulates repository analysis for testing purposes.
        """
        simulated_languages = ["Python", "JavaScript", "TypeScript", "Java", "Go"]
        selected_langs = random.sample(simulated_languages, random.randint(1, 3))

        languages = {}
        for lang in selected_langs:
            languages[lang] = random.randint(100, 5000)

        return {
            "repo_name": repo_name,
            "languages": languages,
            "total_lines": sum(languages.values()),
            "primary_language": max(languages.items(), key=lambda x: x[1])[0],
            "ai_summary": f"Simulated analysis for {repo_name}",
            "analysis_timestamp": datetime.now().isoformat()
        }

    def _ai_summarize_repository(self, repo_name, repo_contents, languages):
        """
        Uses Gemini AI to summarize repository based on its contents.
        """
        if not self.gemini_model or not repo_contents:
            return ""

        # Check cache first
        cache_key = f"{repo_name}_summary"
        if cache_key in self.ai_cache:
            return self.ai_cache[cache_key]

        try:
            # Prepare content for analysis
            content_summary = f"Repository: {repo_name}\n"
            content_summary += f"Languages: {', '.join(languages.keys())}\n\n"

            # Add sample files
            for item in repo_contents[:5]:  # Limit to first 5 files
                content_summary += f"File: {item['name']}\n"
                content_summary += f"Content preview: {item['content'][:500]}...\n\n"

            prompt = f"""
            Analyze this repository and provide a brief, technical summary (2-3 sentences) focusing on:
            - Primary purpose/functionality
            - Key technologies used
            - Notable architectural patterns or approaches

            Repository data:
            {content_summary}
            """

            response = self.gemini_model.generate_content(prompt)
            summary = response.text.strip() if response else ""

            # Cache the result
            self.ai_cache[cache_key] = summary
            return summary

        except Exception as e:
            print(f"AI analysis failed for {repo_name}: {e}")
            return ""

    def _should_exclude_file(self, filename):
        """Check if file should be excluded from analysis."""
        exclude_files = self.config.get("exclusions", {}).get("exclude_files", [])
        for pattern in exclude_files:
            if self._matches_pattern(filename, pattern):
                return True
        return False

    def _get_fallback_repo_data(self, repo_name):
        """Provide fallback data when repository analysis fails."""
        return {
            "repo_name": repo_name,
            "languages": {"Unknown": 1},
            "total_lines": 1,
            "primary_language": "Unknown",
            "ai_summary": f"Analysis unavailable for {repo_name}",
            "analysis_timestamp": datetime.now().isoformat()
        }

    def get_user_repositories(self):
        """Get and cache user repositories."""
        if not self.repositories:
            self.repositories = self.fetch_user_repositories()
        return self.repositories

    def refresh_repositories(self):
        """Force refresh of repositories cache."""
        self.repositories = self.fetch_user_repositories()
        return self.repositories

    def get_tech_stack_mapping(self):
        """
        Returns a mapping of languages to their associated technologies and frameworks.
        """
        return {
            "Python": {"frameworks": ["Django", "Flask", "FastAPI", "Pandas", "NumPy"], "color": "#3776ab", "logo": "python"},
            "JavaScript": {"frameworks": ["React", "Node.js", "Vue.js", "Express"], "color": "#f7df1e", "logo": "javascript"},
            "TypeScript": {"frameworks": ["Angular", "React", "Node.js", "Nest.js"], "color": "#007acc", "logo": "typescript"},
            "Java": {"frameworks": ["Spring", "Spring Boot", "Hibernate", "Maven"], "color": "#ed8b00", "logo": "java"},
            "C#": {"frameworks": [".NET", "ASP.NET", "Entity Framework", "Blazor"], "color": "#239120", "logo": "csharp"},
            "Go": {"frameworks": ["Gin", "Echo", "Fiber", "Gorilla"], "color": "#00add8", "logo": "go"},
            "Rust": {"frameworks": ["Actix", "Rocket", "Warp", "Tokio"], "color": "#000000", "logo": "rust"},
            "PHP": {"frameworks": ["Laravel", "Symfony", "CodeIgniter", "Zend"], "color": "#777bb4", "logo": "php"},
            "Ruby": {"frameworks": ["Ruby on Rails", "Sinatra", "Jekyll", "Hanami"], "color": "#701516", "logo": "ruby"},
            "Swift": {"frameworks": ["SwiftUI", "UIKit", "Vapor", "Perfect"], "color": "#fa7343", "logo": "swift"},
            "Kotlin": {"frameworks": ["Android", "Spring", "Ktor", "Exposed"], "color": "#7f52ff", "logo": "kotlin"},
            "Scala": {"frameworks": ["Akka", "Play", "Spark", "Cats"], "color": "#dc322f", "logo": "scala"},
            "C++": {"frameworks": ["Qt", "Boost", "POCO", "Conan"], "color": "#00599c", "logo": "cplusplus"},
            "C": {"frameworks": ["GLib", "GTK", "SDL", "OpenGL"], "color": "#a8b9cc", "logo": "c"},
            "Dart": {"frameworks": ["Flutter", "AngularDart", "Aqueduct"], "color": "#0175c2", "logo": "dart"},
            "HTML": {"frameworks": ["Bootstrap", "Tailwind CSS", "Bulma"], "color": "#e34f26", "logo": "html5"},
            "CSS": {"frameworks": ["Bootstrap", "Tailwind CSS", "Sass", "Less"], "color": "#1572b6", "logo": "css3"}
        }

    def detect_frameworks_from_repos(self, analysis_results):
        """
        Analyze repositories to detect specific frameworks and technologies.
        """
        detected_frameworks = defaultdict(int)

        for result in analysis_results:
            repo_name = result.get("repo_name", "")
            # This is a simplified detection - in reality, you'd analyze package.json,
            # requirements.txt, pom.xml, etc.

            # Example detection logic based on repository names and languages
            for lang in result.get("languages", {}):
                if lang in self.tech_stack_mapping:
                    frameworks = self.tech_stack_mapping[lang]["frameworks"]
                    for framework in frameworks:
                        # Simple detection based on common patterns
                        if framework.lower() in repo_name.lower():
                            detected_frameworks[framework] += 1

        return detected_frameworks

    def generate_tech_stack_markdown(self, analysis_results):
        """
        Generates a markdown section showcasing the technology stack.
        """
        detected_frameworks = self.detect_frameworks_from_repos(analysis_results)

        if not detected_frameworks:
            return ""

        md = "\n## 🛠️ Technology Stack\n\n"

        # Group by technology type
        web_frameworks = []
        backend_frameworks = []
        data_frameworks = []
        mobile_frameworks = []

        for framework, count in detected_frameworks.items():
            badge = self._format_tech_badge(framework)
            if framework in ["React", "Vue.js", "Angular", "Svelte"]:
                web_frameworks.append(badge)
            elif framework in ["Django", "Flask", "Spring Boot", "Express", ".NET"]:
                backend_frameworks.append(badge)
            elif framework in ["Pandas", "NumPy", "TensorFlow", "PyTorch"]:
                data_frameworks.append(badge)
            elif framework in ["Flutter", "React Native", "SwiftUI"]:
                mobile_frameworks.append(badge)

        if web_frameworks:
            md += "**Frontend:** " + " ".join(web_frameworks) + "\n\n"
        if backend_frameworks:
            md += "**Backend:** " + " ".join(backend_frameworks) + "\n\n"
        if data_frameworks:
            md += "**Data Science:** " + " ".join(data_frameworks) + "\n\n"
        if mobile_frameworks:
            md += "**Mobile:** " + " ".join(mobile_frameworks) + "\n\n"

        return md

    def _format_tech_badge(self, tech_name):
        """Format a technology as a badge."""
        color = self._get_tech_color(tech_name)
        display_name = self._format_tech_display(tech_name)
        return f'<img src="https://img.shields.io/badge/{display_name}-{color}?style=for-the-badge&logo={tech_name.lower()}&logoColor=white" alt="{tech_name}" />'

    def _get_tech_color(self, tech_name):
        """Get the appropriate color for a technology badge."""
        color_map = {
            "React": "61DAFB",
            "Vue.js": "4FC08D",
            "Angular": "DD0031",
            "Django": "092E20",
            "Flask": "000000",
            "Spring Boot": "6DB33F",
            "Express": "000000",
            ".NET": "512BD4",
            "Pandas": "150458",
            "NumPy": "013243",
            "TensorFlow": "FF6F00",
            "PyTorch": "EE4C2C",
            "Flutter": "02569B",
            "React Native": "61DAFB",
            "SwiftUI": "007AFF"
        }
        return color_map.get(tech_name, "333333")

    def _format_tech_display(self, tech_name):
        """Format technology name for display in badge."""
        # Replace spaces and dots for badge compatibility
        return tech_name.replace(" ", "%20").replace(".", "%2E")

    def calculate_user_stats(self, analysis_results):
        """
        Calculate overall user statistics from repository analysis results.
        """
        total_repos = len(analysis_results)
        total_lines = sum(result.get("total_lines", 0) for result in analysis_results)

        # Count unique languages
        all_languages = set()
        for result in analysis_results:
            all_languages.update(result.get("languages", {}).keys())

        return {
            "total_repositories": total_repos,
            "total_lines_of_code": total_lines,
            "total_languages": len(all_languages),
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        }

    def fetch_contribution_activity(self):
        """
        Fetch contribution activity data from GitHub API.
        """
        url = f"https://api.github.com/users/{self.username}/events/public"
        events = self._make_github_request(url)

        if not events:
            return {}

        # Process events to create activity data
        activity_data = defaultdict(int)
        current_time = datetime.now()

        for event in events:
            event_date = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            days_ago = (current_time - event_date).days

            if days_ago <= 365:  # Only last year
                week = days_ago // 7
                if event["type"] in ["PushEvent", "PullRequestEvent", "IssuesEvent"]:
                    activity_data[week] += 1

        return activity_data

    def generate_contribution_svg(self, activity_data):
        """
        Generate a simple ASCII-based contribution graph.
        """
        if not activity_data:
            return ""

        max_contributions = max(activity_data.values()) if activity_data else 1

        graph_lines = []
        for week in range(52):  # 52 weeks in a year
            contributions = activity_data.get(week, 0)
            intensity = min(4, int((contributions / max_contributions) * 4)) if max_contributions > 0 else 0

            # Create a simple representation
            symbols = ["⬜", "🟩", "🟩", "🟩", "🟩"]
            graph_lines.append(symbols[intensity])

        # Group into rows of 12 for better display
        rows = []
        for i in range(0, len(graph_lines), 12):
            rows.append("".join(graph_lines[i:i+12]))

        return "\n".join(rows)

    def generate_contribution_activity_md(self):
        """
        Generate markdown for contribution activity section.
        """
        activity_data = self.fetch_contribution_activity()

        if not activity_data:
            return ""

        total_contributions = sum(activity_data.values())
        active_days = len([days for days in activity_data.values() if days > 0])

        md = "\n## 📊 Contribution Activity\n\n"
        md += f"**This Year:** {total_contributions} contributions across {active_days} active days\n\n"

        # Add simple contribution graph
        contribution_graph = self.generate_contribution_svg(activity_data)
        if contribution_graph:
            md += "```\n"
            md += contribution_graph
            md += "\n```\n"

        return md

    def format_user_stats_markdown(self, user_stats):
        """
        Format user statistics as markdown.
        """
        md = f"**{user_stats['total_repositories']}** repositories • "
        md += f"**{user_stats['total_lines_of_code']:,}** lines of code • "
        md += f"**{user_stats['total_languages']}** languages"
        return md

    def analyze_all_repositories(self):
        """
        Analyzes all repositories for the user.
        """
        if self.use_simulation:
            # Use simulated data for testing
            return [self._simulate_repository_analysis(f"repo-{i}") for i in range(1, 6)]

        repos = self.get_user_repositories()
        if not repos:
            print("No repositories found.")
            return []

        exclude_repos = self.config.get("github", {}).get("exclude_repos", [])
        filtered_repos = [repo for repo in repos if repo["name"] not in exclude_repos]

        print(f"📊 Analyzing {len(filtered_repos)} repositories...")

        analysis_results = []
        for i, repo in enumerate(filtered_repos, 1):
            repo_name = repo["name"]
            print(f"  [{i}/{len(filtered_repos)}] Analyzing {repo_name}...")

            result = self.analyze_repository_structure(repo_name)
            if result:
                analysis_results.append(result)

        print(f"✅ Analysis complete! Processed {len(analysis_results)} repositories.")
        return analysis_results

    def calculate_percentages(self, analysis_results):
        """
        Calculate language percentages across all repositories.
        """
        language_totals = defaultdict(int)

        for result in analysis_results:
            for lang, lines in result.get("languages", {}).items():
                language_totals[lang] += lines

        total_lines = sum(language_totals.values())
        if total_lines == 0:
            return {}

        percentages = {}
        for lang, lines in language_totals.items():
            percentages[lang] = (lines / total_lines) * 100

        return percentages

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
| **Repositories Analyzed** | {user_stats.get('total_repositories', 0)} |
| **Total Lines of Code** | {user_stats.get('total_lines_of_code', 0):,} |
| **Languages Used** | {user_stats.get('total_languages', 0)} |
"""

        # Language ranking
        ranking_md = """| Rank | Language | Usage | Proficiency |
|---|---|---|---|
"""
        for i, item in enumerate(ranking[:5]): # Top 5
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            progress_bar = self._create_progress_bar(item['percentage'])
            ranking_md += f"| {rank_emoji} | **{item['language']}** | `{progress_bar}` {item['percentage']:.1f}% | *{item['level']}* |\n"

        return f"""## 📊 Coding Proficiency Analysis

<table>
<tr>
<td width="40%" valign="top">

{stats_md}

</td>
<td width="60%" valign="top">

{ranking_md}

</td>
</tr>
</table>

<details>
<summary>How is proficiency calculated?</summary>
Proficiency is a weighted score based on commit frequency (40%), lines of code (30%), and repository diversity (30%). Languages must meet minimum thresholds to be included.
</details>
"""

    def _create_progress_bar(self, percentage, length=10):
        """
        Creates a visual progress bar for percentages.
        """
        filled = int((percentage / 100) * length)
        empty = length - filled
        return f"{'█' * filled}{'░' * empty}"

def main():
    """
    Main function to run the script.
    """
    # Ensure all dependencies are installed first
    ensure_dependencies()

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

        # 5. Generate tech stack markdown
        tech_stack_md = analyzer.generate_tech_stack_markdown(analysis_results)

        # 6. Generate contribution activity graph
        contribution_activity_md = analyzer.generate_contribution_activity_md()

        # 7. Generate the full README content
        readme_content = analyzer.generate_profile_readme(ranking, user_stats, tech_stack_md, contribution_activity_md)

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
