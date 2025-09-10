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
        Fetches language data for a specific repository.
        """
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        return self._make_github_request(url) or {}

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
        Generates Markdown for the detected technology stack.
        """
        if not detected_tech:
            return ""

        markdown = "### 💻 Tech Stack\n\n"
        tech_lines = []

        for tech_key in sorted(detected_tech):
            if tech_key in self.tech_stack_mapping:
                display_name, icon_name = self.tech_stack_mapping[tech_key]
                formatted_tech = self._format_tech_display(display_name, icon_name)
                tech_lines.append(formatted_tech)

        # Arrange in columns
        num_columns = 4
        columns = [""] * num_columns
        for i, item in enumerate(tech_lines):
            columns[i % num_columns] += item + "<br>"

        markdown += "<table>\n<tr>\n"
        for col in columns:
            markdown += f'<td valign="top" width="{100//num_columns}%">\n{col}</td>\n'
        markdown += "</tr>\n</table>\n\n"

        return markdown

    def _format_tech_display(self, name, icon, theme='dark'):
        """
        Formats a single technology for display with a Shields.io badge.
        """
        base_url = "https://img.shields.io/badge"
        logo_color = "white"

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
        Calculates a proficiency score for each language.
        """
        lang_quality = defaultdict(list)
        lang_lines = defaultdict(int)

        for result in analysis_results:
            quality = result.get("overall_quality_score", 0)
            if quality > 0:
                total_lines_in_repo = sum(result.get("languages", {}).values())
                if total_lines_in_repo == 0: continue

                for lang, lines in result.get("languages", {}).items():
                    lang_lines[lang] += lines
                    # Weight quality score by language percentage in repo
                    lang_quality[lang].append(quality * (lines / total_lines_in_repo))

        proficiency = {}
        for lang, scores in lang_quality.items():
            avg_quality = sum(scores) / len(scores) if scores else 0
            # Normalize based on lines of code (log scale) and quality
            line_score = min(100, 10 * (len(str(lang_lines[lang])) - 1)) # Simple log-based score
            proficiency[lang] = (avg_quality * 0.7) + (line_score * 0.3)

        return proficiency

    def get_proficiency_level_description(self, score):
        """
        Returns a descriptive level based on a proficiency score.
        """
        if score >= 90: return "🌟 Expert"
        if score >= 75: return "🔥 Proficient"
        if score >= 60: return "💡 Advanced"
        if score >= 40: return "🛠️ Intermediate"
        if score >= 20: return "📚 Competent"
        return "🌱 Novice"

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
        Generates the full README.md content.
        """
        # Header
        readme = f"# Hi, I'm {self.username} 👋\n\n"
        readme += "Welcome to my GitHub profile! Here's a dynamically generated overview of my recent activity and language proficiency.\n\n"

        # Stats and Ranking
        readme += "<table><tr>\n"
        readme += f'<td valign="top" width="50%">\n{self.format_user_stats_markdown(user_stats)}</td>\n'
        readme += f'<td valign="top" width="50%">\n{self.format_ranking_markdown(ranking)}</td>\n'
        readme += "</tr></table>\n\n"

        # Tech Stack
        readme += tech_stack_md

        # Footer
        readme += "---\n"
        readme += f"*{self.get_random_citation()}*\n\n"
        readme += f"<p align='center'><i>Last updated: {self.get_current_timestamp()}</i></p>\n"

        return readme

    def format_ranking_markdown(self, ranking):
        """
        Formats the language ranking into a Markdown table.
        """
        if not ranking:
            return "### 🏆 Language Ranking\n\nNo language data to display.\n"

        markdown = "### 🏆 Language Ranking\n\n"
        markdown += "| Rank | Language     | Usage | Proficiency Level |\n"
        markdown += "|------|--------------|-------|-------------------|\n"

        for item in ranking:
            markdown += f"| {item['rank']} | {item['language']:<12} | {item['percentage']:.2f}% | {item['level']} |\n"

        return markdown

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
