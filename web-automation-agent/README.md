# Hybrid AI Web Automation Agent

An intelligent browser automation agent that visits a URL, classifies the page as a **form** or **MCQ quiz**, fills/solves it using a local LLM, clicks the next button, and repeats until the flow is complete.

All AI inference runs **100% locally** via [Ollama](https://ollama.com/) — no API keys, no cloud calls.

---

## Features

- **Auto page detection** — classifies pages as FORM or MCQ using `qwen3:8b`
- **Smart form filling** — uses your data first, falls back to LLM-generated realistic values
- **MCQ solving** — groups radio/checkbox questions, asks the LLM, clicks the answer
- **Multi-page looping** — follows Next / Continue / Submit buttons automatically
- **Session state** — persists actions and answers to JSON for inspection / resume
- **Debug mode** — optional screenshots after each navigation step
- **Graceful fallbacks** — heuristic classification when Ollama is unavailable
- **Headless or visible** — toggle with `--headless`

---

## Project Structure

```
web-automation-agent/
├── main.py                  # CLI entry point
├── requirements.txt
├── agents/
│   ├── __init__.py
│   ├── controller.py        # Orchestration loop + browser lifecycle
│   ├── page_analyzer.py     # Page classification (FORM | MCQ | UNKNOWN)
│   ├── form_filler.py       # Fill input fields and submit
│   ├── mcq_solver.py        # Extract questions and click correct answers
│   └── navigator.py         # Find and click Next/Submit buttons
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Shared logging factory (console + file)
│   ├── ollama_client.py     # ask_llm() wrapper for qwen3:8b
│   └── helpers.py           # retry_with_backoff, DOM extraction, screenshots
├── config/
│   ├── __init__.py
│   └── settings.py          # All tuneable constants (env-overridable)
└── outputs/
    ├── screenshots/         # Debug screenshots (written at runtime)
    ├── logs/                # Session log files (written at runtime)
    └── session_state.json   # Action history (written at runtime)
```

---

## Quick Start

### 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| [Ollama](https://ollama.com/download) | Latest |
| Chromium (via Playwright) | Installed below |

### 2. Install Python dependencies

```bash
cd web-automation-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 3. Install and start Ollama

```bash
# Download from https://ollama.com/download, then:
ollama pull qwen3:8b
ollama serve          # starts the local API at http://localhost:11434
```

> Ollama usually starts automatically. Run `ollama serve` only if it is not already running.

---

## Usage

### Basic — auto-detect mode (default)

```bash
python main.py --url https://httpbin.org/forms/post
```

### Force form-filling with custom data

```bash
python main.py --url https://httpbin.org/forms/post --mode form \
  --user-data '{"custname": "Alice Smith", "custtel": "555-1234", "custemail": "alice@example.com"}'
```

### Solve an MCQ quiz with debug screenshots

```bash
python main.py --url https://example.com/quiz --mode mcq --screenshot
```

### Run headless (no browser window)

```bash
python main.py --url https://example.com/form --headless
```

---

## CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--url` | *(required)* | Target URL to automate |
| `--mode` | `auto` | `form` \| `mcq` \| `auto` — how to handle each page |
| `--headless` | `false` | Run browser without a visible window |
| `--screenshot` | `false` | Save a PNG after each navigation step |
| `--user-data` | `{}` | JSON object of field name/label → value pairs |

---

## Configuration

All settings live in `config/settings.py` and can be overridden with environment variables or a `.env` file placed in the project root.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen3:8b` | Model to use for all LLM calls |
| `MAX_PAGES` | `20` | Maximum pages to process per run |
| `MAX_RETRIES` | `3` | Consecutive failures before aborting |
| `NAVIGATION_TIMEOUT` | `30000` | Playwright timeout in milliseconds |
| `WAIT_AFTER_ACTION` | `1.5` | Seconds to wait between actions |
| `HEADLESS` | `false` | Default browser visibility |
| `DEBUG_SCREENSHOTS` | `false` | Save screenshots by default |
| `LLM_CONTEXT_MAX_CHARS` | `3000` | Max DOM characters sent to the LLM |
| `SESSION_STATE_PATH` | `outputs/session_state.json` | Where to persist session state |

---

## Agent Architecture

```
main.py (argparse)
    └─► ControllerAgent.run(url, mode, user_data)
            │
            ├─[1] browser.goto(url)
            │
            └─[loop — up to MAX_PAGES]
                    │
                    ├─[auto mode] PageAnalyzerAgent.analyze(page) → FORM | MCQ | UNKNOWN
                    │
                    ├─[FORM / mode=form] FormFillerAgent.fill(page, user_data)
                    │
                    ├─[MCQ / mode=mcq]   MCQSolverAgent.solve(page)
                    │
                    ├─[all modes]        NavigatorAgent.navigate(page) → True | False
                    │                    False = no next button → loop ends
                    │
                    └─[each step]        _save_state() → outputs/session_state.json
```

### Agent Responsibilities

| Agent | File | Role |
|---|---|---|
| **ControllerAgent** | `agents/controller.py` | Browser lifecycle, loop, sub-agent dispatch, state persistence |
| **PageAnalyzerAgent** | `agents/page_analyzer.py` | DOM analysis + LLM classification of page type |
| **FormFillerAgent** | `agents/form_filler.py` | Field discovery, value resolution, form submission |
| **MCQSolverAgent** | `agents/mcq_solver.py` | Question extraction, LLM answering, option clicking |
| **NavigatorAgent** | `agents/navigator.py` | Next/Submit button detection and page transition |

---

## Session State

After each run, `outputs/session_state.json` records:

```json
{
  "start_url": "https://example.com/quiz",
  "current_url": "https://example.com/quiz/done",
  "page_number": 3,
  "run_started_at": "2026-04-01T10:00:00",
  "actions": [
    {
      "page_number": 1,
      "url": "https://example.com/quiz",
      "page_type": "MCQ",
      "success": true,
      "timestamp": "2026-04-01T10:00:05"
    }
  ],
  "answers": {}
}
```

---

## Known Limitations

- **iframes** — form fields or buttons inside cross-origin iframes are not reachable with standard Playwright locators.
- **JavaScript-heavy SPAs** — pages that load content dynamically after the initial `networkidle` may require increasing `NAVIGATION_TIMEOUT` or `WAIT_AFTER_ACTION`.
- **CAPTCHA** — not supported. The agent will log a warning and attempt to navigate past the page.
- **File upload fields** — `input[type=file]` are skipped by `FormFillerAgent`.
- **Multi-step authentication** — the agent does not bypass login walls. Start the URL from an already-authenticated session or a page that does not require auth.

---

## Tech Stack

| Component | Library | Version |
|---|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) | ≥ 1.40 |
| Local LLM | [Ollama](https://ollama.com/) + [ollama-python](https://github.com/ollama/ollama-python) | ≥ 0.1.7 |
| Model | qwen3:8b | — |
| Config | python-dotenv | ≥ 1.0 |

---

## Future Improvements

- **Resume interrupted sessions** — reload `session_state.json` and continue from the last URL
- **Multi-browser support** — add Firefox and WebKit via `playwright` flags
- **Async mode** — refactor to `async_playwright` for parallel page processing
- **Custom prompt templates** — allow users to supply their own LLM prompts via config
- **Pytest test suite** — add integration tests using a local HTML fixture server
- **Streaming LLM responses** — show real-time LLM output for long answers
- **Form data profiles** — load `user_data` from a JSON file instead of CLI flag
