# Discord Chatbot

A Discord chatbot using Groq's free API tier.

## Description
This is a prototype Discord bot that uses Discord API.

## Getting Started

### Requirements

- Python 3.8 or higher
- Discord Bot Token
- Groq API key (free at [Groq Console](https://console.groq.com/keys))

### How To Install

1. Clone this repository:
```bash
git clone [repository-url]
cd discord-chatbot
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create `.env` file and set your Discord Bot Token:
```
DISCORD_TOKEN=your_token_here
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.6-27b
```

### How To Run

```bash
python main.py
```

If `GROQ_API_KEY` is omitted, the bot still starts but AI chat commands stay disabled.

### Synology Container Manager

1. Copy the repository into a NAS shared folder.
2. Copy `.env.example` to `.env` and fill in `DISCORD_TOKEN` and `GROQ_API_KEY`.
3. In Container Manager, create a project from `compose.yaml`.

The container runs as an unprivileged user and restarts automatically unless stopped manually.

## License

Copyright (c) 2024 Gloryciel

All rights reserved.

This project is proprietary and confidential. Unauthorized copying, distribution, or use of this project, via any medium, is strictly prohibited. This project is for personal use only and may not be used, modified, or distributed without explicit permission from the author. 
