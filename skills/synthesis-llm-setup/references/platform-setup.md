# LLM setup: platform steps

Setup steps for each platform. Instructions come from `compiled/{project}/instructions/`; knowledge comes from `all-knowledge.md`.

## Claude Projects setup

### Custom instructions

1. Create a new Claude Project (or open an existing one).
2. Go to Project Knowledge, then Custom Instructions.
3. Copy content from `compiled/{project}/instructions/claude.md`.
4. Paste into the custom instructions field.

### Knowledge files

**Option A: GitHub sync (recommended)**
1. Connect your GitHub account to Claude.
2. Sync the repository containing your ai-knowledge repo.
3. Claude indexes `all-knowledge.md` and source files automatically.

**Option B: Manual upload**
1. Go to Project Knowledge, then Files.
2. Upload `all-knowledge.md` from the repo root.

## ChatGPT GPT setup

### Creating a GPT

1. Go to https://chat.openai.com/gpts/editor
2. Click "Create a GPT".
3. Configure:
   - **Name**: Your project name
   - **Description**: Brief description
   - **Instructions**: Copy from `compiled/{project}/instructions/chatgpt.md`

### Knowledge files

1. In the GPT editor, go to the Knowledge section.
2. Upload `all-knowledge.md` from the repo root.

## Gemini Gems setup

### Creating a Gem

1. Go to https://gemini.google.com/gems
2. Create a new Gem.
3. Paste instructions from `compiled/{project}/instructions/gemini.md`.

### Knowledge files

1. Upload `all-knowledge.md` from the repo root.
2. This single file contains all runbooks and datasets merged together.
3. Works well within Gemini's 10-file limit per Gem.

## Other LLMs (Grok, etc.)

1. Copy instructions from `compiled/{project}/instructions/` (use the closest match).
2. Upload `all-knowledge.md` from the repo root.
