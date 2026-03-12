# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo contains **Aria**, a terminal-based AI therapist chatbot using Ollama (local LLM) with the LLaMA 3.2 model.

## Setup

```bash
pip install ollama
ollama pull llama3.2
```

Ollama must be running locally before launching the chatbot.

## Running

```bash
python aria-therapist/aria_therapist.py
```

## Architecture

Single-file script (`aria-therapist/aria_therapist.py`):
- Uses `ollama.chat()` with `stream=True` for real-time token output
- Maintains full conversation history in a `messages` list (OpenAI-style format)
- A hardcoded `SYSTEM_PROMPT` defines Aria's therapist persona
- No external config, no persistence — conversation resets on each run

## Model

- Model: `llama3.2` via Ollama (local, no API key needed)
- To swap models, change the `model` parameter in the `ollama.chat()` call
