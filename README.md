# update-profile-stats-script

A Python script that automatically generates comprehensive GitHub profile statistics including tech stack categorization, user metrics, and programming language rankings.

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

## Usage

```bash
python3 script.py
```

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