# Master plan

Goal: a team of AI agents that produces unique, engaging 10-15 minute narrated films with character dialogue
for a global English YouTube audience. No fixed genre. Minimal spend at the start. A human approves every
film before it is published.

Two entry modes feed one pipeline:

- **Mode A (Discover):** the system researches trends and proposes the best ideas.
- **Mode B (Your topic):** you give a topic, the system researches it and builds the film.

## Agent team (15 agents plus a human gate)

| # | Agent | Job | Phase |
| --- | --- | --- | --- |
| 0 | Orchestrator | Runs the pipeline, holds shared state, retries, enforces budget | 1 |
| 1 | Trend Scout | Scans HN, Reddit, YouTube for rising themes; proposes ranked ideas | 1 |
| 2 | Researcher | Builds a cited dossier | 1 |
| 3 | Ideation Expert | Turns the dossier into 5 distinct concepts | 1 |
| 4 | Originality Checker | Rejects near-duplicates of existing work | 1 |
| 5 | Story Architect | Beat sheet, hook, retention turns | 1 |
| 6 | Scriptwriter | Scene-by-scene narration and dialogue | 1 |
| 7 | Script Critic | Scores the script, sends scene-level fixes back | 1 |
| 8 | Visual Director | Style bible, character sheets, shot list | 2 |
| 9 | Asset Generator | Images per shot, per-shot quality check | 2 |
| 10 | Voice and Sound | Narrator and character voices, music, effects, mix | 2 |
| 11 | Editor | FFmpeg assembly, captions, runtime check | 2 |
| 12 | Reviewer | Scores the final film against a rubric | 3 |
| 13 | Packaging | Titles, thumbnails, description, chapters | 3 |
| 14 | Publisher and Analyst | Upload after approval, track retention, feed lessons back | 4 |

## Pipeline

1. Intake (Mode A or B)
2. Research
3. Ideation and originality check
4. Story and script, with a critic loop (max 3 rounds)
5. Visual planning
6. Production (images, voices, music)
7. Edit
8. Review (max 2 loops, then escalate to the human)
9. Packaging
10. Human gate: approve, reject or request changes
11. Publish with the AI-content disclosure set
12. Learn from retention and click-through data

## Near-zero budget format: Motion Story

Instead of paid video generation, each film is built from generated still images (about 70-100 for 12 minutes)
animated with pans, zooms and parallax in FFmpeg, plus narration, character voices, music and captions.
Upgrade path: add short image-to-video clips for key scenes only, once a film proves its retention.

| Layer | Near-zero option |
| --- | --- |
| Orchestration | Plain Python (later LangGraph or Temporal) |
| Language models | Ollama local models; a paid model only for script stages if wanted |
| Images | Local Stable Diffusion on the GPU (RTX 3050 Ti, 4 GB) or free cloud GPU sessions |
| Voices | Open-source TTS (Piper, Kokoro), one voice per character |
| Music | Royalty-free libraries |
| Captions | Whisper |
| Assembly | FFmpeg |
| Publishing | YouTube Data API |

Check every tool's current licence allows commercial use before monetising.

## Script quality gate

The Script Critic scores 6 criteria from 1 to 10: originality, hook, story, dialogue, pacing, emotion.
A script passes when the average is at least 8, no single score is below 6, and the estimated runtime
is inside the 10-15 minute window. Runtime is computed in code, not by the model.

## Risks

- YouTube policy on mass-produced or repetitive content. Unique stories and human review are the protection. Check current Partner Program rules before launch.
- Label realistic synthetic content using the YouTube disclosure setting.
- Copyright: no existing characters, franchises, real people or unlicensed music.
- Fact errors: every factual claim must trace to a source in the dossier.
- Cost: the orchestrator enforces a token budget and stops the run.
- Sameness: genre rotation and a strict Originality Checker counter drift to the average.

## Roadmap

| Phase | Weeks | Build | Checkpoint |
| --- | --- | --- | --- |
| 1. Brain | 1-2 | Idea, research, story, script agents | 7 of 10 scripts you rate better than a quick draft of your own |
| 2. Look and sound | 3-4 | Visual Director, images, voices, music, FFmpeg edit | A 2-minute test scene with consistent characters across 20 shots |
| 3. Film | 5-6 | Reviewer, Packaging, full 10-12 minute film end to end | One film you would publish |
| 4. Channel | 7-8 | Dashboard, human gate, Publisher, Analyst feedback loop | Retention above 40% over the first 3 minutes on 3 films |
