# Beginner guide: make your first film script, from zero

This guide assumes you have never used a terminal, Git or Python. It is written for a Windows laptop with an NVIDIA RTX 3050 Ti. Follow the steps in order. Do not skip the checks: each one tells you the step worked.

## What you will get, and what you will not

You will get a researched, scored film script (about 10-15 minutes of narration and character dialogue) saved as files on your laptop. You will not get a video yet. Images, voices and the video edit are phase 2, which is not built.

Time needed: about 1 hour of setup the first time, then 1-2 hours of waiting for the first script (my estimate). Cost: $0.

## Words you will see

- **Terminal (PowerShell):** a window where you type commands instead of clicking. Windows already has it.
- **Command:** one line you type, then press Enter.
- **Repository (repo):** a project folder stored on GitHub.
- **Clone:** download a repo to your laptop.
- **Python:** the programming language this project is written in.
- **Virtual environment (venv):** a private box for this project's Python packages, so they do not mix with anything else.
- **Ollama:** a free program that runs AI models on your own laptop.
- **Model:** the AI brain Ollama runs. `qwen2.5:3b` is small and fast. `qwen2.5:7b` is bigger and writes better but is slower.

## Part 1: Check your laptop

1. **Free disk space.** Open File Explorer, click "This PC", and look at drive C:. You need at least 15 GB free. The models alone are several GB.
2. **Update your NVIDIA driver.** Open the Start menu, type "GeForce Experience" or "NVIDIA App", open it and install any driver update. If you have neither, go to nvidia.com/drivers, choose your card (GeForce RTX 3050 Ti Laptop GPU), and install the latest driver. This lets Ollama use your graphics card.
3. **Plug in the charger.** The run is long and heavy. Set Windows power mode to "Best performance" in Settings, System, Power.

## Part 2: Install three programs

### 2.1 Python

1. Go to python.org/downloads and click the yellow "Download Python" button.
2. Run the downloaded file.
3. **On the first screen, tick the box "Add python.exe to PATH".** This is the most common thing people miss.
4. Click "Install Now" and wait for "Setup was successful". Click Close.

### 2.2 Git

1. Go to git-scm.com/download/win. The download starts by itself.
2. Run the file. Click Next on every screen and accept the defaults. Click Install, then Finish.

### 2.3 Ollama

1. Go to ollama.com/download and download the Windows installer.
2. Run it and click Install. When it finishes, Ollama runs in the background. You may see a small llama icon near the clock at the bottom right. That is normal.

## Part 3: Open a terminal and check the installs

1. Click the Start menu, type `PowerShell`, and open "Windows PowerShell". A blue or black window appears with a line ending in `>`. This is where you type.
2. Type each command below, press Enter after each, and compare with what you should see.

```
python --version
```
You should see `Python 3.` followed by numbers, such as `Python 3.12.4`. Any 3.10 or newer is fine.

```
git --version
```
You should see `git version 2.` and numbers.

```
ollama --version
```
You should see a version line.

If any command says "is not recognized", close PowerShell, open a new one, and try again. If it still fails, restart the laptop and try again. For Python, the usual cause is the unticked PATH box: run the Python installer again, choose "Modify", and reinstall with the box ticked.

## Part 4: Download the project

1. Go to your Documents folder. In PowerShell type:
```
cd $HOME\Documents
```
2. Download the project:
```
git clone https://github.com/sadhakcuj/AI-YT-Studio.git
```
3. Go inside the project folder:
```
cd AI-YT-Studio
```
You should now see `PS C:\Users\<your name>\Documents\AI-YT-Studio>`. Every command from here on must be typed while you are inside this folder.

## Part 5: Set up the project's Python box

1. Create the virtual environment (takes about 30 seconds):
```
python -m venv .venv
```
2. Turn it on:
```
.venv\Scripts\activate
```
You should now see `(.venv)` at the start of the line. That means it is on.

If you get a red error about "running scripts is disabled", type this once, answer `Y` if asked, then repeat step 2:
```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
3. Install the packages the project needs (takes a few minutes, lots of text scrolls by, that is normal):
```
pip install -r requirements.txt
```
It ends with a line starting `Successfully installed`.

## Part 6: Download the AI models

Keep the terminal open. These downloads are large, so use a good Wi-Fi connection.

```
ollama pull qwen2.5:3b
```
About 2 GB. Wait for `success`.

```
ollama pull qwen2.5:7b
```
About 4-5 GB. Wait for `success`.

**Check that Ollama works:**
```
ollama run qwen2.5:3b "Say hello in five words"
```
You should get a short reply within a minute. If you see an error about a connection, Ollama is not running: open the Start menu, type `Ollama`, open it, wait 10 seconds, and try again.

## Part 7: Create your settings file

```
copy .env.example .env
```
You do not need to edit it now. Leave it as it is.

## Part 8: Check that everything works

```
python -m pytest
```
You should see `7 passed`. This test uses a pretend AI and does not need Ollama, so it proves the project code installed correctly. If it fails, copy the red text and send it to me.

## Part 9: Make your first film script

Pick one option.

**Option A: you choose the topic.**
```
python -m studio.cli topic "The strange history of the Voynich manuscript"
```
Keep the quote marks. Replace the words inside them with any topic you like.

**Option B: let the AI find an idea from trends.**
```
python -m studio.cli discover
```
It shows 8 ideas. Type a number (for example `3`) and press Enter. Or press Enter alone for idea 1. If you want it to choose the best one with no questions, add `--auto`:
```
python -m studio.cli discover --auto
```

**What you will see.** A line `Run <date-time-code> (topic)`, then short progress lines such as `Researcher: gathering sources`, `Ideation Expert: generating 5 concepts`, `Scriptwriter: writing scene 1.1`, `Script Critic: scoring round 1`. Write down or copy the run code from the first line.

**How long.** My estimate is 1-2 hours with the 7b model. The window may look frozen for several minutes between lines. That is normal: the laptop is thinking. Do not close the window. Your fans will be loud.

**To speed it up** (lower quality): open the file `config\settings.yaml` in Notepad (`notepad config\settings.yaml`), find the line `smart_model: qwen2.5:7b`, change `7b` to `3b`, save, and start the run again.

The run ends with: `Done: script_ready. Output in runs/<run code>/`. If it says `script_needs_review`, the script did not reach the quality score after 3 rounds. The best version is still saved, and the report lists what the critic did not like.

## Part 10: Read your script

1. Open the output folder:
```
explorer runs
```
2. Open the folder named with your run code. Inside:
   - `script.md`: **the film script. Read this first.** Open it with Notepad.
   - `report.md`: critic scores, estimated runtime, tokens used, and the log.
   - `dossier.md`: the research notes.
   - `script.json`: the same script for the computer. Phase 2 will use it.
   - `state.json`: the full saved run.
3. Check: does it have a gripping start, characters who sound different from each other, and a satisfying ending? Is the estimated runtime between 10 and 15 minutes?

## Part 11: If the run stops or crashes

Type this, replacing the code with yours:
```
python -m studio.cli resume 20261113-201500-ab12
```
It continues from the last finished step. It does not start over.

## Part 12: Coming back another day

Each time you open a fresh PowerShell, type these three lines first:
```
cd $HOME\Documents\AI-YT-Studio
.venv\Scripts\activate
git pull
```
`git pull` downloads any updates I have pushed. Then run your commands.

## Problems and fixes

| What you see | What it means | Fix |
| --- | --- | --- |
| `python is not recognized` | Python is not on PATH | Reinstall Python with "Add python.exe to PATH" ticked, then open a new PowerShell |
| `No module named 'studio'` or `No module named 'pydantic'` | You are in the wrong folder or the box is off | `cd $HOME\Documents\AI-YT-Studio`, then `.venv\Scripts\activate` |
| `Connection refused` or `All connection attempts failed` | Ollama is not running | Open Ollama from the Start menu, wait 10 seconds, run again |
| `model 'qwen2.5:7b' not found` | Model not downloaded | `ollama pull qwen2.5:7b` |
| `Model failed to return JSON` | The small model wrote broken output | Run `resume <run code>`; if it keeps happening, switch to `3b`, or ask me to tune the prompts |
| Very slow, or a memory error | 7b is too big for 4 GB graphics memory | Change `smart_model` to `qwen2.5:3b` in `config\settings.yaml` |
| `Stopped on token budget` | The safety limit of 400,000 tokens was reached | `resume <run code>` after raising `max_llm_tokens_per_run` in `config\settings.yaml` |
| Scripts feel flat or generic | Small local models are limited | Try the paid-model option below |

If anything else goes wrong, copy the full red error text and send it to me. Do not retype it: exact text matters.

## Optional upgrades

**Better trend and originality checks (free).** Get a YouTube Data API key: sign in at console.cloud.google.com, create a project, enable "YouTube Data API v3", create an API key under Credentials. Open `.env` in Notepad (`notepad .env`) and write the key after `YOUTUBE_API_KEY=`, with nothing else on that line. Save. Never share this key or post it online.

**Better scripts (small cost).** Get an Anthropic API key from console.anthropic.com, add credit (start with $5), and write the key after `ANTHROPIC_API_KEY=` in `.env`. Then in `config\settings.yaml` change `provider_smart: ollama` to `provider_smart: anthropic`. Only the story, script and critic stages then use the paid model. I estimate $1-4 per film but have not measured it. Check current prices on their site.

## What to send me after your first run

1. The text of `report.md`.
2. The first page of `script.md`.
3. How long the run took.
4. Anything that went wrong, copied exactly.

With that I tune the prompts and give you a real measured cost, then build phase 2 to turn the script into a video.
