# AI-YT-Studio

An automated team of AI agents for making YouTube films. Full plan: [docs/PLAN.md](docs/PLAN.md). New to all this? Start with the [beginner guide](docs/BEGINNER_GUIDE.md). Licence: MIT.

Automated team of AI agents that turns an idea (found from live trends, or given by you) into a finished,
quality-checked film script for a 10-15 minute narrated YouTube film with character dialogue.

Phase 1 (this code): idea, research, story, script. Output is `script.json`, which phase 2 (images, voices,
music, edit) will read. Phase 1 costs nothing if you run it on a local model.

## Agents in phase 1

| Agent | File | Job |
| --- | --- | --- |
| Trend Scout | `agents/trend_scout.py` | Reads Hacker News, Reddit, YouTube trending; proposes 8 ranked ideas, rotating genres |
| Researcher | `agents/researcher.py` | Builds a cited dossier from Wikipedia |
| Ideation Expert + Originality Checker | `agents/ideation.py` | 5 concepts, rejects near-duplicates of existing videos |
| Story Architect | `agents/story_architect.py` | Beat sheet, hook, retention turns, scene plan |
| Scriptwriter | `agents/scriptwriter.py` | Writes scene by scene, narration plus dialogue |
| Script Critic | `agents/critic.py` | Scores 6 criteria, checks runtime, sends scene-level fixes back |

`graph.py` runs them in order. The script loop repeats up to 3 rounds. A run stops cleanly at the token budget and can be resumed.

## Setup (Windows, macOS or Linux)

1. Install Python 3.10+ and [Ollama](https://ollama.com).
2. Pull small models that fit a 4 GB GPU (RTX 3050 Ti):
   ```
   ollama pull qwen2.5:3b
   ollama pull qwen2.5:7b
   ```
   The 7b model is slower on 4 GB (part runs on CPU) but writes better scripts. If too slow, set `smart_model` to `qwen2.5:3b` in `config/settings.yaml`.
3. Install and configure:
   ```
   pip install -r requirements.txt
   cp .env.example .env
   ```
4. Optional: add `YOUTUBE_API_KEY` to `.env` (free, from Google Cloud Console) for YouTube trends and originality search.

## Run

```
python -m studio.cli topic "The strange history of the Voynich manuscript"   # Mode B
python -m studio.cli discover                                               # Mode A, you pick
python -m studio.cli discover --auto                                        # Mode A, fully automatic
python -m studio.cli resume <run_id>                                        # continue a stopped run
```

Output goes to `runs/<run_id>/`: `script.md` (read it), `script.json` (for phase 2), `dossier.md`, `report.md`, `state.json`.

## Better scripts for a few dollars

Local small models write average scripts. In `config/settings.yaml` set `provider_smart: anthropic` and put
`ANTHROPIC_API_KEY` in `.env`. Only the story, script and critic stages use the smart tier. Keep
`provider_fast: ollama` so research and trend work stays free. Check current API prices first.

## Tests

```
python -m pytest
```

Tests use a scripted fake LLM: no network, no GPU, no cost.

## Safety and quality checks

Found after the first real run, which produced an invented, false story about real religious figures. Now:

- The Researcher plans its searches, filters irrelevant pages, and a Fact Checker strips dossier lines the sources do not state.
- Real-world rules go to every creative agent: no invented words, beliefs or crimes for real people, no anachronisms, no links between real subjects that the sources do not make. Use fictional characters inside real settings.
- The critic reports accuracy issues. Any one blocks the quality gate.
- Code-level checks block the gate on unknown speakers, long character monologues, narration scenes that contain character lines, and dialogue share outside 20-80%.
- A rewrite that scores worse is thrown away. The best draft is always kept.
- `report.md` starts with a "Read before use" list of warnings. A film about real people or beliefs is always flagged for a human fact check.

## Known limits

- The Ollama adapter and the free data sources have been run once on a real laptop. The Anthropic adapter has not been run for real. Expect to tune prompts.
- Small local models sometimes return broken JSON. The router retries twice, then fails the stage; use `resume`.
- The originality check only works with `YOUTUBE_API_KEY`. Without it, the report says so.
- Small local models write weak, repetitive scripts. A script that fails the gate after 3 rounds is expected on a 7b model; use a stronger model for the story, script and critic stages.
- Ollama's default context window is small. `config/settings.yaml` sets `num_ctx: 8192` so the critic sees the whole script. Lower it to 4096 if you get memory errors.

## Roadmap

Phase 2: Visual Director, style bible, image generation (local Stable Diffusion on the GPU), Voice and Sound (Piper or Kokoro),
FFmpeg Editor. Phase 3: Reviewer, Packaging. Phase 4: dashboard, human gate, Publisher, Analyst.
