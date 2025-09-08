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
    
    def analyze_all_repositories(self) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
        """Analyze all repositories and return language statistics."""
        print(f"Analyzing repositories for user: {self.username}")
        repos = self.get_user_repositories()
        print(f"Found {len(repos)} repositories")
        
        total_languages = defaultdict(int)
        language_repos = defaultdict(list)
        
        for repo in repos:
            repo_name = repo['name']
            languages = repo.get('languages', [])
            
            if languages:
                print(f"Repository: {repo_name} -> {', '.join(languages)}")
                for language in languages:
                    if language:  # Skip empty language entries
                        estimated_bytes = self.estimate_language_bytes(language)
                        total_languages[language] += estimated_bytes
                        language_repos[language].append(repo_name)
            else:
                print(f"Repository: {repo_name} -> No languages detected")
        
        return dict(total_languages), dict(language_repos)
    
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
        
        language_stats, language_repos = self.analyze_all_repositories()
        
        # Filter out excluded languages
        filtered_stats = {
            lang: bytes_count for lang, bytes_count in language_stats.items()
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
        
        return {
            'total_repositories': len(repos),
            'owned_repositories': len(owned_repos),
            'contributed_repositories': len(contributed_repos),
            'language_stats': filtered_stats,
            'language_percentages': percentages,
            'language_repositories': language_repos,
            'ranking': sorted_languages,
            'excluded_languages': exclude_languages,
            'excluded_repositories': [repo['name'] for repo in self.config.get('excluded_repositories', [])]
        }
    
    def format_ranking_markdown(self, ranking_data: Dict) -> str:
        """Format the ranking data as markdown."""
        md = []
        md.append("## 🔥 Programming Language Rankings\n")
        md.append(f"*Based on analysis of {ranking_data['total_repositories']} repositories ({ranking_data['owned_repositories']} owned + {ranking_data['contributed_repositories']} contributed)*\n")
        
        if not ranking_data['ranking']:
            md.append("No language data available.\n")
            return "\n".join(md)
        
        for i, (language, bytes_count) in enumerate(ranking_data['ranking'][:10], 1):
            percentage = ranking_data['language_percentages'][language]
            repo_count = len(ranking_data['language_repositories'][language])
            
            # Create progress bar (visual representation)
            bar_length = max(1, int(percentage / 100 * 20))  # Ensure at least 1 char for small percentages
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            md.append(f"{i}. **{language}** - {percentage:.1f}% ({repo_count} repos)")
            md.append(f"   `{bar}` {bytes_count:,} bytes\n")
        
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
