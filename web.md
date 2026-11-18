# ViciCat

Local-first LLM application and game categorizer for the Vicinae launcher with Google Gemini fallback.

## Key Features
- **Native Vicinae Extension:** Generates `@vicinae/api` commands per category (`Games`, `Development`, `Media`, etc.) and a filtered browser.
- **Live Usage Sorting:** Sorts categories and apps by launch frequency and recency from Vicinae `metadata.json`.
- **Local-First LLM + Cloud Fallback:** Uses Ollama or OpenAI-compatible servers (`llama-swap`) first, falling back to Google Gemini REST API.
- **Zero-Token Game Fast-Path:** Classifies Steam, Lutris, and Heroic `.desktop` launchers as `Games` without LLM calls.
- **Background Auto-Grouping:** Ships `systemd --user` `.path` and `.timer` units to categorize newly installed apps automatically.

## Tech Stack
- **Backend:** Python 3, REST API (`requests`)
- **Launcher:** Vicinae (`@vicinae/api`)
- **LLM:** Ollama (`gemma4:26b-a4b-it-qat`), `llama-swap`, Google Gemini API
- **Automation:** `systemd --user`
