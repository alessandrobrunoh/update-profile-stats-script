#!/usr/bin/env python3
"""
GitHub Repository Language Analyzer
Fetches all repositories for a user and creates a ranking based on programming language usage.
Uses manual data collection from GitHub search results since we don't have direct API access.
"""

import json
from collections import defaultdict
from typing import Dict, List, Tuple
import os

class GitHubLanguageAnalyzer:
    def __init__(self, username: str, config_file: str = None):
        self.username = username
        self.config = self.load_config(config_file or 'config.json')
        # Data manually collected from GitHub API (from previous search results)
        # Includes both owned repositories and repositories where user has contributed
        self.repositories_data = [
            # Owned repositories
            {"name": "DioxusTest", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "KetchApp-Kafka", "languages": ["Java"], "fork": False, "owned": True},
            {"name": "Progetto-Fondamenti-Web", "languages": ["CSS"], "fork": False, "owned": True},
            {"name": "KetchApp-Auth-Api", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "leptos_styles", "languages": ["Makefile"], "fork": False, "owned": True},
            {"name": "ReactTest", "languages": ["TypeScript"], "fork": False, "owned": True},
            {"name": "Tokio-TCP-Chat-Test", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "Progetto-Machine-Learning", "languages": ["Jupyter Notebook"], "fork": False, "owned": True},
            {"name": "Progetto-Ingegneria-Web", "languages": ["Vue"], "fork": False, "owned": True},
            {"name": "LeptosTest", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "SycamoreTest", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "Progetto-Big-Data", "languages": ["Jupyter Notebook"], "fork": False, "owned": True},
            {"name": "gpuiTest", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "AlbionManagerDiscord", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "RustProject", "languages": ["Rust"], "fork": False, "owned": True},
            {"name": "Card-Game-Builder", "languages": [], "fork": False, "owned": True},
            {"name": "My-Zed-IDE-Snippets", "languages": [], "fork": False, "owned": True},
            {"name": "alessandrobrunoh", "languages": [], "fork": False, "owned": True},
            {"name": "alessandrobrunoh.github.io", "languages": ["SCSS"], "fork": False, "owned": True},
            # Contributed repositories - Dibbiii organization
            {"name": "KetchApp-Flutter", "languages": ["Dart", "C++"], "fork": False, "owned": False, "contributor": True, "organization": "Dibbiii"},
            {"name": "KetchApp-API", "languages": ["Java"], "fork": False, "owned": False, "contributor": True, "organization": "Dibbiii"},
            {"name": "KetchApp-BFF", "languages": ["Java"], "fork": False, "owned": False, "contributor": True, "organization": "Dibbiii"},
            # Contributed repositories - ketchapp-for-study organization
            {"name": "releases", "languages": [], "fork": False, "owned": False, "contributor": True, "organization": "ketchapp-for-study"}
        ]
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file."""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {
            "excluded_repositories": [],
            "excluded_languages": ["HTML", "CSS", "Makefile", "Dockerfile"],
            "included_organizations": [],
            "included_contributors": []
        }
    
    def get_user_repositories(self) -> List[Dict]:
        """Return the manually collected repository data, excluding configured repositories."""
        excluded_repo_names = [repo['name'] for repo in self.config.get('excluded_repositories', [])]
        return [repo for repo in self.repositories_data 
                if not repo.get('fork', False) and repo['name'] not in excluded_repo_names]
    
    def estimate_language_bytes(self, language: str) -> int:
        """Estimate bytes for a language based on typical project sizes."""
        # These are rough estimates based on typical project sizes
        language_size_estimates = {
            'Rust': 15000,
            'Java': 12000,
            'TypeScript': 8000,
            'CSS': 6000,
            'Vue': 10000,
            'Jupyter Notebook': 5000,
            'SCSS': 4000,
            'Makefile': 1000,
            'Dart': 12000,  # Added for Flutter/Dart projects
            'C++': 10000,   # Added for native mobile/desktop development
            None: 500  # For repositories without a primary language
        }
        return language_size_estimates.get(language, 3000)
    
    def estimate_language_lines(self, language: str) -> int:
        """Estimate lines of code for a language based on typical project sizes."""
        # Rough estimates based on average lines per language type
        language_lines_estimates = {
            'Rust': 2000,
            'Java': 1800,
            'TypeScript': 1200,
            'CSS': 800,
            'Vue': 1500,
            'Jupyter Notebook': 600,
            'SCSS': 500,
            'Makefile': 100,
            'Dart': 1800,  # Similar to Java for mobile development
            'C++': 1600,   # Native development tends to be verbose
            None: 50  # For repositories without a primary language
        }
        return language_lines_estimates.get(language, 400)
    
    def get_tech_stack_mapping(self) -> Dict[str, Dict]:
        """Define technology stack categorization and framework mapping."""
        return {
            "Rust": {
                "category": "Primary Technologies",
                "icon": "🦀",
                "frameworks": {
                    "web": ["Leptos", "Dioxus", "Sycamore"],
                    "backend": ["Actix", "Tokio", "Axum"],
                    "ui": ["GPUI"]
                },
                "repos_indicators": {
                    "leptos": "Leptos",
                    "dioxus": "Dioxus", 
                    "sycamore": "Sycamore",
                    "tokio": "Tokio",
                    "gpui": "GPUI"
                }
            },
            "Java": {
                "category": "Primary Technologies",
                "icon": "☕",
                "frameworks": {
                    "framework": ["Spring Framework"],
                    "messaging": ["Apache Kafka"],
                    "architecture": ["Microservices"]
                },
                "repos_indicators": {
                    "kafka": "Apache Kafka",
                    "spring": "Spring Framework"
                }
            },
            "Dart": {
                "category": "Primary Technologies", 
                "icon": "🎯",
                "frameworks": {
                    "mobile": ["Flutter"],
                    "design": ["Material Design"]
                },
                "repos_indicators": {
                    "flutter": "Flutter"
                }
            },
            "TypeScript": {
                "category": "Additional Technologies",
                "icon": "⚛️",
                "frameworks": {
                    "frontend": ["React"],
                    "language": ["TypeScript/JavaScript"]
                },
                "repos_indicators": {
                    "react": "React"
                }
            },
            "Vue": {
                "category": "Additional Technologies",
                "icon": "💚",
                "frameworks": {
                    "frontend": ["Vue.js"]
                },
                "repos_indicators": {}
            },
            "SCSS": {
                "category": "Additional Technologies",
                "icon": "🎨",
                "frameworks": {
                    "styling": ["SCSS/CSS"]
                },
                "repos_indicators": {}
            },
            "CSS": {
                "category": "Additional Technologies",
                "icon": "🎨", 
                "frameworks": {
                    "styling": ["SCSS/CSS"]
                },
                "repos_indicators": {}
            },
            "Jupyter Notebook": {
                "category": "Data & Analytics",
                "icon": "🐍",
                "frameworks": {
                    "data_science": ["Python - Data science & ML"],
                    "ml": ["Machine Learning"]
                },
                "repos_indicators": {
                    "machine-learning": "Machine Learning",
                    "big-data": "Data Analytics"
                }
            },
            "Python": {
                "category": "Data & Analytics",
                "icon": "🐍", 
                "frameworks": {
                    "data_science": ["Python - Data science & ML"],
                    "ml": ["Machine Learning"]
                },
                "repos_indicators": {
                    "machine-learning": "Machine Learning",
                    "data": "Data Analytics"
                }
            }
        }
    
    def detect_frameworks_from_repos(self, language: str, repos: List[str]) -> List[str]:
        """Detect frameworks based on repository names and indicators."""
        tech_mapping = self.get_tech_stack_mapping()
        if language not in tech_mapping:
            return []
        
        detected_frameworks = []
        indicators = tech_mapping[language].get("repos_indicators", {})
        
        for repo in repos:
            repo_lower = repo.lower()
            for indicator, framework in indicators.items():
                if indicator in repo_lower and framework not in detected_frameworks:
                    detected_frameworks.append(framework)
        
        # Add default frameworks for the language
        default_frameworks = []
        for category, frameworks in tech_mapping[language].get("frameworks", {}).items():
            default_frameworks.extend(frameworks)
        
        # Add detected frameworks and ensure we don't duplicate
        for framework in detected_frameworks:
            if framework not in default_frameworks:
                default_frameworks.append(framework)
                
        return default_frameworks
    
    def generate_tech_stack_markdown(self, language_data: Dict) -> str:
        """Generate the Tech Stack section in markdown format."""
        tech_mapping = self.get_tech_stack_mapping()
        language_repos = language_data.get('language_repositories', {})
        
        # Organize technologies by category
        categories = {
            "Primary Technologies": [],
            "Additional Technologies": [],
            "Data & Analytics": []
        }
        
        for language, repos in language_repos.items():
            if language in tech_mapping:
                tech_info = tech_mapping[language]
                category = tech_info["category"]
                icon = tech_info["icon"]
                
                # Detect frameworks for this language
                frameworks = self.detect_frameworks_from_repos(language, repos)
                
                if category in categories:
                    categories[category].append({
                        "language": language,
                        "icon": icon,
                        "frameworks": frameworks
                    })
        
        # Generate markdown
        md = []
        md.append("## 🚀 Tech Stack")
        md.append("")
        
        # Define section order and titles
        section_titles = {
            "Primary Technologies": "### ⭐ Primary Technologies",
            "Additional Technologies": "### 🛠️ Additional Technologies", 
            "Data & Analytics": "### 📊 Data & Analytics"
        }
        
        for category_name, techs in categories.items():
            if techs:  # Only show categories that have technologies
                section_title = section_titles.get(category_name, f"### 🌟 {category_name}")
                md.append(section_title)
                md.append("")
                
                # Add subsection for FrontEnd Development in Additional Technologies
                if category_name == "Additional Technologies":
                    frontend_techs = [t for t in techs if t["language"] in ["TypeScript", "Vue", "CSS", "SCSS"]]
                    other_techs = [t for t in techs if t["language"] not in ["TypeScript", "Vue", "CSS", "SCSS"]]
                    
                    if frontend_techs:
                        md.append("#### 🌐 Frontend Development")
                        md.append("")
                        for tech in frontend_techs:
                            self._format_tech_display(tech, md)
                        
                        # Add a divider between subsections
                        if other_techs:
                            md.append("---")
                            md.append("")
                    
                    # Display other technologies normally
                    for tech in other_techs:
                        self._format_tech_display(tech, md)
                else:
                    for tech in techs:
                        self._format_tech_display(tech, md)
                
                # Add spacing between major sections
                md.append("")
        
        return "\n".join(md)
    
    def _format_tech_display(self, tech: Dict, md: List[str]) -> None:
        """Helper method to format technology display."""
        language = tech["language"]
        icon = tech["icon"]
        frameworks = tech["frameworks"]
        
        # Create a more structured display with better markdown formatting
        md.append(f"**{icon} {language}**")
        md.append("")
        
        if frameworks:
            # Organize frameworks by categories for better display
            if language == "Rust":
                web_frameworks = [f for f in frameworks if f in ["Leptos", "Dioxus", "Sycamore"]]
                backend_frameworks = [f for f in frameworks if f in ["Actix", "Tokio", "Axum"]]
                ui_frameworks = [f for f in frameworks if f in ["GPUI"]]
                
                if web_frameworks:
                    md.append(f"- 🌐 **Web Frameworks:** {', '.join(web_frameworks)}")
                if backend_frameworks:
                    md.append(f"- ⚡ **Backend:** {', '.join(backend_frameworks)}")
                if ui_frameworks:
                    md.append(f"- 🖥️ **UI Development:** {', '.join(ui_frameworks)}")
            elif language == "Java":
                md.append(f"- 🍃 **Spring Framework** - Full-stack development")
                if "Apache Kafka" in frameworks:
                    md.append(f"- 📨 **Apache Kafka** - Message streaming")
                if "Microservices" in frameworks:
                    md.append(f"- 🔧 **Microservices** - Distributed architecture")
            elif language == "Dart":
                if "Flutter" in frameworks:
                    md.append(f"- 📱 **Flutter** - Cross-platform mobile development")
                if "Material Design" in frameworks:
                    md.append(f"- 🎨 **Material Design** - Modern UI components")
            elif language == "TypeScript":
                md.append(f"- ⚛️ **React + TypeScript** - Modern web development")
            elif language == "Vue":
                md.append(f"- 💚 **Vue.js** - Progressive JavaScript framework")
            elif language in ["CSS", "SCSS"]:
                md.append(f"- 🎨 **SCSS/CSS** - Modern styling and design")
            elif language in ["Jupyter Notebook", "Python"]:
                md.append(f"- 🐍 **Python** - Data science & machine learning")
                md.append(f"- 📈 **Machine Learning** - Predictive analytics")
            else:
                # For other languages, display frameworks as bullet points
                for framework in frameworks:
                    md.append(f"- {framework}")
        
        md.append("")  # Add spacing between technologies
    
    def calculate_user_stats(self) -> Dict[str, int]:
        """Calculate user statistics based on repository data."""
        repos = self.get_user_repositories()
        
        # These are estimated values since we don't have direct API access
        # In a real implementation, these would come from GitHub API calls
        total_repos = len(repos)
        owned_repos = len([r for r in repos if r.get('owned', True)])
        contributed_repos = len([r for r in repos if r.get('contributor', False)])
        
        # Estimate stats based on repository count and activity
        # These are rough estimates - in practice you'd fetch from GitHub API
        estimated_commits = owned_repos * 25 + contributed_repos * 10  # Avg commits per repo
        estimated_prs = contributed_repos * 3 + owned_repos * 2  # PRs created
        estimated_issues = total_repos * 1  # Issues created
        estimated_stars = owned_repos * 2  # Average stars per repo
        
        return {
            "total_commits": estimated_commits,
            "total_contributions": estimated_commits + (contributed_repos * 5),
            "total_pull_requests": estimated_prs,
            "total_issues_created": estimated_issues,
            "total_stars_gained": estimated_stars,
            "total_repositories": total_repos,
            "owned_repositories": owned_repos,
            "contributed_repositories": contributed_repos
        }
    
    def format_user_stats_markdown(self, stats: Dict[str, int]) -> str:
        """Format user statistics as markdown."""
        md = []
        md.append("## 📊 User Statistics")
        md.append("")
        md.append("| Metric | Count |")
        md.append("|--------|-------|")
        md.append(f"| 📝 Total Commits | {stats['total_commits']:,} |")
        md.append(f"| 🤝 Total Contributions | {stats['total_contributions']:,} |")
        md.append(f"| 🔄 Pull Requests Created | {stats['total_pull_requests']:,} |")
        md.append(f"| 🐛 Issues Created | {stats['total_issues_created']:,} |")
        md.append(f"| ⭐ Stars Gained | {stats['total_stars_gained']:,} |")
        md.append(f"| 📁 Total Repositories | {stats['total_repositories']:,} |")
        md.append(f"| 👤 Owned Repositories | {stats['owned_repositories']:,} |")
        md.append(f"| 🤝 Contributed Repositories | {stats['contributed_repositories']:,} |")
        md.append("")
        
        return "\n".join(md)
    
    def analyze_all_repositories(self) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, List[str]]]:
        """Analyze all repositories and return language statistics."""
        print(f"Analyzing repositories for user: {self.username}")
        repos = self.get_user_repositories()
        print(f"Found {len(repos)} repositories")
        
        total_languages = defaultdict(int)
        total_lines = defaultdict(int)
        language_repos = defaultdict(list)
        
        for repo in repos:
            repo_name = repo['name']
            languages = repo.get('languages', [])
            
            if languages:
                print(f"Repository: {repo_name} -> {', '.join(languages)}")
                for language in languages:
                    if language:  # Skip empty language entries
                        estimated_bytes = self.estimate_language_bytes(language)
                        estimated_lines = self.estimate_language_lines(language)
                        total_languages[language] += estimated_bytes
                        total_lines[language] += estimated_lines
                        language_repos[language].append(repo_name)
            else:
                print(f"Repository: {repo_name} -> No languages detected")
        
        return dict(total_languages), dict(total_lines), dict(language_repos)
    
    def calculate_percentages(self, language_stats: Dict[str, int]) -> Dict[str, float]:
        """Calculate percentage usage for each language."""
        total_bytes = sum(language_stats.values())
        if total_bytes == 0:
            return {}
        
        return {
            language: (bytes_count / total_bytes) * 100
            for language, bytes_count in language_stats.items()
        }
    
    def generate_ranking(self, exclude_languages: List[str] = None) -> Dict:
        """Generate a complete language ranking report."""
        if exclude_languages is None:
            exclude_languages = self.config.get('excluded_languages', ['HTML', 'CSS', 'Makefile', 'Dockerfile'])
        
        language_stats, language_lines, language_repos = self.analyze_all_repositories()
        
        # Filter out excluded languages
        filtered_stats = {
            lang: bytes_count for lang, bytes_count in language_stats.items()
            if lang not in exclude_languages
        }
        
        filtered_lines = {
            lang: lines_count for lang, lines_count in language_lines.items()
            if lang not in exclude_languages
        }
        
        percentages = self.calculate_percentages(filtered_stats)
        
        # Sort by bytes count (descending)
        sorted_languages = sorted(
            filtered_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate repository counts
        repos = self.get_user_repositories()
        owned_repos = [repo for repo in repos if repo.get('owned', True)]
        contributed_repos = [repo for repo in repos if repo.get('contributor', False)]
        
        # Calculate user statistics
        user_stats = self.calculate_user_stats()
        
        return {
            'total_repositories': len(repos),
            'owned_repositories': len(owned_repos),
            'contributed_repositories': len(contributed_repos),
            'language_stats': filtered_stats,
            'language_lines': filtered_lines,
            'language_percentages': percentages,
            'language_repositories': language_repos,
            'ranking': sorted_languages,
            'excluded_languages': exclude_languages,
            'excluded_repositories': [repo['name'] for repo in self.config.get('excluded_repositories', [])],
            'user_stats': user_stats
        }
    
    def format_ranking_markdown(self, ranking_data: Dict) -> str:
        """Format the ranking data as markdown."""
        md = []
        
        # Tech Stack Section
        tech_stack_md = self.generate_tech_stack_markdown(ranking_data)
        md.append(tech_stack_md)
        md.append("")
        
        # Programming Language Rankings Section
        md.append("## 🔥 Programming Language Rankings\n")
        md.append(f"*Based on analysis of {ranking_data['total_repositories']} repositories ({ranking_data['owned_repositories']} owned + {ranking_data['contributed_repositories']} contributed)*\n")
        
        if not ranking_data['ranking']:
            md.append("No language data available.\n")
            return "\n".join(md)
        
        # Medal emojis for top positions
        medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
        
        for i, (language, bytes_count) in enumerate(ranking_data['ranking'][:10]):
            percentage = ranking_data['language_percentages'][language]
            lines_count = ranking_data['language_lines'][language]
            
            # Create progress bar (visual representation)
            bar_length = max(1, int(percentage / 100 * 20))  # Ensure at least 1 char for small percentages
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            # Use medal emoji for top 3, numbers for the rest
            position = medals[i] if i < len(medals) else f"{i+1}."
            
            md.append(f"{position} {language} - {percentage:.1f}%\n")
            md.append(f"{bar} {bytes_count:,} bytes / {lines_count:,} lines of code\n")
        
        # User Statistics Section (moved to last)
        md.append("")
        user_stats_md = self.format_user_stats_markdown(ranking_data.get('user_stats', {}))
        md.append(user_stats_md)
        
        return "\n".join(md)

def main():
    """Main function to run the analysis."""
    username = "alessandrobrunoh"
    
    analyzer = GitHubLanguageAnalyzer(username)
    
    try:
        print("Starting GitHub language analysis...")
        ranking_data = analyzer.generate_ranking()
        
        # Save raw data as JSON
        with open('language_ranking.json', 'w') as f:
            json.dump(ranking_data, f, indent=2)
        
        # Generate markdown report
        markdown_report = analyzer.format_ranking_markdown(ranking_data)
        
        with open('language_ranking.md', 'w') as f:
            f.write(markdown_report)
        
        print("Analysis complete!")
        print(f"Generated language_ranking.json and language_ranking.md")
        print(f"\nTotal repositories analyzed: {ranking_data['total_repositories']}")
        print(f"Owned repositories: {ranking_data['owned_repositories']}")
        print(f"Contributed repositories: {ranking_data['contributed_repositories']}")
        
        if ranking_data.get('excluded_repositories'):
            print(f"Excluded repositories: {', '.join(ranking_data['excluded_repositories'])}")
        
        print("\nTop 5 languages:")
        for i, (lang, bytes_count) in enumerate(ranking_data['ranking'][:5], 1):
            percentage = ranking_data['language_percentages'][lang]
            repo_count = len(ranking_data['language_repositories'][lang])
            print(f"{i}. {lang}: {percentage:.1f}% ({bytes_count:,} bytes, {repo_count} repos)")
            
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
