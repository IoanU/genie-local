#Genie Local CLI — Offline AI Shell Assistant

A fully offline, privacy‑safe CLI assistant that generates, explains, and refines Bash commands using **Ollama** and open‑source language models (like *Mistral*, *Phi3*, or *Llama3*). Ideal for local environments where you want an AI assistant without API keys or cloud dependencies.

---

## Installation

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

### 2. Download a Local Model

Pick one depending on your hardware:

```bash
ollama pull mistral      # Balanced, recommended default
# or
ollama pull phi3:3.8b     # Small, fast, great for CPU-only
# or
ollama pull llama3:8b     # Smarter, but heavier (GPU recommended)
```

### 3. Install Genie Local

Save the `genie_local.py` script and make it executable:

```bash
chmod +x genie_local.py
sudo mv genie_local.py /usr/local/bin/genie-local
```

### 4. (Optional) Add Aliases

```bash
echo 'alias ai="genie-local"' >> ~/.bashrc
echo 'alias ai-run="genie-local --mode run"' >> ~/.bashrc
echo 'alias ai-x="genie-local --mode explain"' >> ~/.bashrc
echo 'export GENIE_MODEL="mistral"' >> ~/.bashrc
source ~/.bashrc
```

---

## eatures

### Generate Commands (default)

Turn natural language into valid Bash commands.

```bash
genie-local "list files modified in the last 2 days"
```

Output example:

```bash
find . -type f -mtime -2
```

---

### Run Commands with Confirmation (`--mode run`)

Generates a command and asks for confirmation before executing it.

```bash
genie-local --mode run "find all .mp4 files larger than 1GB under ~/Videos"
```

* Prompts before execution.
* Automatically offers **refine** mode if the command fails (based on stderr).

---

### Explain Commands (`--mode explain`)

Summarizes what a command does in 2–4 bullet points.

```bash
genie-local --mode explain --cmd "find . -type f -mtime -2"
```

Or explain the last generated command:

```bash
genie-local --mode explain --use-last
```

---

### Refine Commands (`--mode refine`)

Improve incorrect or non‑portable commands, either manually or automatically.

#### Manual refine:

```bash
genie-local --mode refine --use-last --why "macOS find doesn’t support -printf; use -exec stat instead"
```

#### Auto refine after failure:

```bash
genie-local --mode refine --use-last
```

#### Refine with a new task:

```bash
genie-local --mode refine "list largest 10 files recursively" --why "previous command didn’t sort by size"
```

---

## Command-Line Options

| Option         | Description                                         |
| -------------- | --------------------------------------------------- |
| `--model`      | Choose Ollama model (e.g. `phi3:3.8b`, `llama3:8b`) |
| `--mode`       | One of `suggest`, `run`, `explain`, or `refine`     |
| `--shell`      | Shell used for execution (`/bin/bash`, `/bin/zsh`)  |
| `--no-history` | Disable history logging                             |
| `--use-last`   | Use the last saved task/command                     |
| `--why`        | Explain what went wrong for refine mode             |

---

## Persistent Files

| File                        | Description                                     |
| --------------------------- | ----------------------------------------------- |
| `~/.genie_local_state.json` | Stores last command, task, and any error output |
| `~/.genie_local_history`    | Keeps a full log of generated commands          |

---

## Safety

* Detects dangerous command patterns (e.g. `rm -rf /`, `mkfs`, `reboot`).
* Requires explicit `YES` confirmation to execute risky commands.

---

## Recommended Models

| Model       | RAM Required       | Notes                           |
| ----------- | ------------------ | ------------------------------- |
| `phi3:3.8b` | 4–6 GB             | Light, fast, CPU‑friendly       |
| `mistral`   | 8–16 GB            | Balanced, reliable, default     |
| `llama3:8b` | 16 GB+ (GPU ideal) | Strong reasoning, slower on CPU |

---

## How It Works

1. Prompts a local Ollama model with your natural‑language task.
2. Normalizes the output (removes code fences/backticks).
3. Filters potentially dangerous commands.
4. Saves the result in history and state.
5. Lets you run, explain, or refine the command interactively.

---

## Quick Examples

```bash
# Generate a command
ai "show disk usage by folder"

# Explain the last command
ai-x --use-last

# Run with confirmation
ai-run "kill all firefox processes"

# Auto-refine after an error
ai-run "du -sh * | sort -h"

# Manual refine
ai --mode refine --use-last --why "du doesn’t have -h option on BusyBox"
```

---

## Development Guide

1. Clone or fork this repository.
2. Modify or extend the command parsing in `genie_local.py`.
3. Test locally using `ollama run mistral` or any other model.
4. Submit pull requests for new features or model integrations.

---

### License

MIT License — free for personal and commercial use.

