# Market Watch Bot

AI-assisted weekly market analysis and monitoring bot.

Market Watch Bot uses [TradingAgents](https://github.com/TauricResearch/TradingAgents) and OpenRouter-compatible LLMs to analyze a configurable watchlist and deliver the results through Telegram.

The project is designed as a personal experiment in **AI-assisted software development and automated maintenance workflows**.

## How it works

```text
Watchlist
    ↓
TradingAgents
    ↓
LLM-based market analysis
    ↓
Investment signal extraction
    ↓
Markdown report
    ↓
Telegram notification
```

The workflow runs automatically through GitHub Actions on a weekly schedule.

## Features

* Configurable stock watchlist
* Automated weekly analysis
* OpenRouter model selection with fallback models
* Automatic retry for rate-limited models
* Markdown report generation
* JSON summary generation
* Telegram notifications
* GitHub Actions automation
* Unit tests for core parsing and report-generation logic

## AI Model Handling

The project can try multiple LLM candidates and automatically select an available model.

This is particularly useful when using free or rate-limited model endpoints, where availability can change over time.

Models are configured in `config.json` and can be changed without modifying the main Python code.

## Configuration

The watchlist and model candidates are configured in:

```text
config.json
```

Example:

```json
{
  "watchlist": {
    "Technology": ["NVDA", "MSFT"],
    "ETF": ["VOO", "QQQ"]
  }
}
```

The current repository configuration is intentionally kept small for testing.

## Required Secrets

The following GitHub Actions secrets are required:

| Secret               | Purpose                     |
| -------------------- | --------------------------- |
| `OPENROUTER_API_KEY` | LLM API access              |
| `TELEGRAM_BOT_TOKEN` | Telegram bot authentication |
| `TELEGRAM_CHAT_ID`   | Destination chat            |

Secrets are read from environment variables and are not stored in the repository.

> Never commit API keys, bot tokens, passwords, or other credentials to the repository.

## Running Locally

```bash
git clone https://github.com/Byung-Jun/market-watch-bot.git
cd market-watch-bot

python -m venv .venv
```

Activate the virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

Set the required environment variables:

```bash
export OPENROUTER_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

Then run:

```bash
python run_watchlist.py
```

## Testing

Run the unit tests with:

```bash
python -m unittest discover
```

The repository currently includes tests for:

* Investment signal extraction
* Rate-limit handling
* Model fallback selection
* Report generation

## GitHub Actions

The workflow is located at:

```text
.github/workflows/weekly.yml
```

It can be triggered automatically by the weekly schedule or manually using `workflow_dispatch`.

The workflow:

1. Installs dependencies
2. Runs the watchlist analysis
3. Generates reports
4. Commits generated reports
5. Sends the result to Telegram

## AI-Assisted Development

This project is also an experiment in applying AI to the broader software development lifecycle.

AI-assisted development is being explored for:

* Requirement analysis
* Code generation
* Refactoring
* Debugging
* Test generation
* Code review
* Documentation
* Issue analysis
* Maintenance automation

The long-term goal is to understand how coding agents can assist an individual maintainer with both **development and ongoing software maintenance**.

## Roadmap

* [ ] Expand the default watchlist
* [ ] Improve report validation
* [ ] Add more robust data-quality checks
* [ ] Expand automated tests
* [ ] Improve GitHub issue automation
* [ ] Add AI-assisted issue triage
* [ ] Add AI-assisted pull request review
* [ ] Automate release notes and changelog generation
* [ ] Document the AI-assisted maintenance workflow

## Disclaimer

This project is for research and educational purposes only.

The generated reports are not financial advice and should not be used as the sole basis for investment decisions.

Financial data and AI-generated analysis may contain errors or inaccuracies. Always independently verify information before making financial decisions.

## License

MIT License
