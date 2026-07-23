# 🎪 David's Claude Code Marketplace

> _Where AI meets productivity magic!_ ✨

Welcome to my personal collection of Claude Code plugins, skills, and MCP servers. Each tool is crafted to supercharge specific workflows with AI-powered automation. 🚀

---

## 🌟 What's Inside?

This marketplace is your one-stop shop for Claude Code extensions that make life easier, work smarter, and development faster!

### 🔌 Available Plugins

| Plugin                                      | Description                            | What It Does                                                                    | Status   |
| ------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------- | -------- |
| 💰 **[Monarch Money](#-monarch-money)**     | Budget management & receipt splitting  | Split receipts by category, categorize transactions, manage finances through AI | ✅ Ready |
| 🖼️ **[Image Search](#️-image-search)**      | Unsplash image discovery               | Describe any image and instantly find it from the internet                      | ✅ Ready |
| 🐙 **[github-dev-flow](./github-dev-flow/)** | GitHub issue lifecycle & dev workflow | Create issues with evidence, manage project boards, worktree-isolated planning  | ✅ Ready |
| 📐 **[linear-dev-flow](./linear-dev-flow/)** | Linear issue lifecycle & dev workflow  | Plan in Todo, implement from Dev Ready, deliver to In Review                     | ✅ Ready |
| 🤝 **[ask-models](#-ask-models)**           | Second opinions from other AI models   | Orchestrate Claude, Codex/GPT, Cursor models & Antigravity/Gemini with live JSONL streams | ✅ Ready |
| 🧭 **[fable](#-fable)**                     | Strategic advice & orchestration       | Consult Fable 5 or run durable, bounded Ask Codex worker programs              | ✅ Ready |
| 🎬 **[media-tools](#-media-tools)**         | Audio, video & image tooling           | Transcribe/diarize recordings, clean VTT, generate/edit images (Gemini & OpenAI) | ✅ Ready |
| 🌐 **[browser-tools](#-browser-tools)**     | Stealth browser automation             | Real Chrome + your profile to get past CAPTCHAs / bot detection                 | ✅ Ready |
| 🧰 **[dev-utils](#-dev-utils)**             | Everyday developer utilities           | Git worktrees & styled Mermaid diagrams                                         | ✅ Ready |
| 🔬 **[research-tools](#-research-tools)**   | Research & knowledge tools             | NotebookLM API & YouTube search with insights                                   | ✅ Ready |

---

## 💰 Monarch Money

**Split receipts like a pro and manage your budget with AI!**

### ✨ Features

- 📸 **Receipt Splitting** - Upload receipt images and automatically split by category
- 🔍 **Transaction Search** - Find transactions by date, merchant, or amount
- 📊 **Category Management** - View and manage budget categories with smart caching
- ✏️ **Quick Updates** - Modify transactions, merchants, amounts, and notes
- 🎯 **Pre-flight Validation** - Catch errors before they hit your budget
- ⚡ **Lightning Fast** - Category caching and optimized API calls

### 🎭 What You Can Say

```
"Split this Walmart receipt into groceries and household items"
"Find my Target transaction from October 16th"
"What categories are available in Monarch Money?"
"Add itemized notes to transaction XYZ"
"Update this transaction to the Dining Out category"
```

### 🛠️ Tech Stack

- **Language:** TypeScript
- **API:** Monarch Money GraphQL
- **Scripts:** 6 specialized npm scripts
- **Features:** Category caching, validation, automated notes

### 📚 Documentation

- [SKILL.md](./monarch-money/skills/monarch-money-handling/SKILL.md) - Quick start guide
- [SCRIPTS_REFERENCE.md](./monarch-money/skills/monarch-money-handling/SCRIPTS_REFERENCE.md) - Detailed script docs
- [TROUBLESHOOTING.md](./monarch-money/skills/monarch-money-handling/TROUBLESHOOTING.md) - Common issues & solutions

---

## 🖼️ Image Search

**Describe it, find it, use it - all through natural language!**

### ✨ Features

- 🎨 **Natural Language Search** - Just describe what you want
- 📥 **Auto Download** - Images saved directly to your system
- 🌐 **Unsplash Integration** - Access millions of high-quality photos
- 🔌 **MCP Server** - Built on Model Context Protocol for seamless integration

### 🎭 What You Can Say

```
"Find me an image of a sunset over mountains"
"I need a picture of a friendly animal"
"Search for professional office workspace photos"
"Get me a cozy coffee shop interior image"
```

### 🛠️ Tech Stack

- **Language:** Python
- **API:** Unsplash API
- **Protocol:** MCP (Model Context Protocol)
- **Server:** Custom Python MCP server

### 📚 Documentation

- [Plugin Config](./image-search/.claude-plugin/plugin.json) - Plugin metadata
- [MCP Server](./image-search/local-mcp/unsplash-mcp-server/) - Server implementation

---

## 🤝 ask-models

**Phone a friend — get a second opinion from a different model.**

Each skill wraps another AI CLI for orchestration: kick a partner off in the background, watch its JSONL event stream to tell "still thinking" from "hung," then collect the clean final answer.

- 🧠 **ask-claude** — Claude Opus (`claude --print --output-format stream-json`)
- 🤖 **ask-codex** — OpenAI Codex / GPT (`codex exec --json`, high reasoning effort)
- 🎯 **ask-cursor** — any Cursor-hosted model (Opus, GPT, Gemini, Grok, Composer…)
- 🛰️ **ask-antigravity** — Google's Antigravity CLI (Gemini 3.x, and more)

```
"Ask codex why this migration might fail"
"Get a second opinion from Opus on the auth refactor"
"Have cursor's gpt-5.4 and gemini both review this in parallel"
```

> Requires the respective partner CLIs installed (`claude`, `codex`, `cursor-agent`, `agy`).

---

## 🧭 fable

**Use Fable 5 for a hard decision—or let it orchestrate a sustained program.**

- 🧠 **fable-advisor** — read-only strategic consultation for consequential,
  uncertain decisions
- 🗂️ **fable-orchestrator** — durable plans, bounded Ask Codex worker waves,
  explicit approval gates, crash recovery, and budget enforcement

```
"Ask Fable to challenge this migration plan"
"Manage this multi-workstream project with Fable as orchestrator"
```

> Requires Cursor's `agent` CLI with Fable 5 access. Orchestrated programs also
> require the `ask-codex` skill from `ask-models`.

---

## 🎬 media-tools

**Recordings in, clean text and images out.**

- 🎙️ **transcribe** — voice notes, meetings, video → text. Groq Whisper (fast/free), xAI for large files, Deepgram Nova-3 for multi-speaker diarization
- 🧹 **vtt-processor** — clean WebVTT (Teams/Zoom) into token-efficient, speaker-attributed text (~62% smaller)
- 🍌 **nanobanana-image-gen** — generate/edit images via Gemini (gcloud OAuth or `GEMINI_API_KEY`)
- 🖼️ **codex-image-gen** — generate/edit/compose images via OpenAI Codex (gpt-image)

```
"Transcribe this meeting and tell me who said what"
"Clean up this Teams .vtt transcript"
"Generate a logo of a ceramic coffee cup, photorealistic"
```

---

## 🌐 browser-tools

**Get past the bouncer.**

- 🥷 **stealth-browser** — launches real Google Chrome with your profile for bot-detected / CAPTCHA / login-required sites (Google, Cloudflare-protected pages) when standard headless automation gets blocked

```
"This site keeps blocking the headless browser — use stealth-browser to log in and screenshot my dashboard"
```

---

## 🧰 dev-utils

**The small tools you reach for constantly.**

- 🌳 **git-worktree** — isolated worktrees with `.worktreeinclude` copy support for gitignored secrets
- 📊 **mermaid-diagram-builder** — styled, validated Mermaid diagrams for markdown

```
"Make a worktree for this feature branch"
"Build a sequence diagram of the auth handshake"
```

---

## 🔬 research-tools

**Go deep on a topic.**

- 📓 **notebooklm** — full programmatic NotebookLM (notebooks, sources, podcasts & other artifacts)
- ▶️ **yt-search** — structured YouTube search with view counts, dates & auto-insights

```
"Create a NotebookLM podcast about this PDF"
"Search YouTube for recent talks on this topic"
```

---

## 🚀 Getting Started

### Prerequisites

- **Claude Code/Desktop etc.** installed and configured
- **Node.js 18+** (for TypeScript plugins)
- **Python 3.11+** (for Python plugins)
- API keys for specific services (Monarch Money, Unsplash, etc.)

### Installation

1. **Add this marketplace to Claude Code:**

   In your Claude Code settings file (`~/.claude/settings/settings.json`), add this marketplace to the `marketplaces` array:

   ```json
   {
     "marketplaces": [
       {
         "name": "davideasaf-marketplace",
         "source": "https://github.com/davideasaf/davideasaf-marketplace.git"
       }
     ]
   }
   ```

   Or use the marketplace installation command:
   ```bash
   # Add marketplace via Claude Code
   /marketplace add https://github.com/davideasaf/davideasaf-marketplace.git
   ```

2. **Configure plugin-specific credentials:**

   **Monarch Money:**

   ```bash
   export MONARCH_EMAIL="your-email"
   export MONARCH_PASSWORD="your-password"
   ```

   **Image Search:**

   ```bash
   export UNSPLASH_ACCESS_KEY="your-access-key"
   ```

3. **Start using the plugins naturally in Claude Code:**
   ```
   "Find my recent Walmart transactions"
   "Search for sunset mountain images"
   ```

---

## 🎯 Usage Tips

### 💡 Pro Tips

- 🗣️ **Speak Naturally** - All plugins understand conversational language
- 🔄 **Combine Powers** - Use multiple plugins together for powerful workflows
- 📖 **Read the Docs** - Each plugin has detailed documentation in its directory
- 🐛 **Check Troubleshooting** - Most issues have quick fixes in the guides

### 🎪 Fun Workflows

**Budget + Images:**

```
"Find my Home Depot receipt from last week and show me images of
similar home improvement projects"
```

**Financial Planning:**

```
"Show me my dining out transactions from last month and find images
of healthy meal prep ideas"
```

---

## 📁 Repository Structure

```
davideasaf-marketplace/
├── 📄 README.md                        # You are here! 👋
├── 📄 .gitignore                       # Keep secrets safe
├── ⚙️ .claude-plugin/
│   └── marketplace.json                # Marketplace config
├── 💰 monarch-money/
│   ├── .claude-plugin/plugin.json
│   └── skills/monarch-money-handling/
│       ├── SKILL.md                    # Main skill guide
│       ├── SCRIPTS_REFERENCE.md        # Detailed docs
│       ├── TROUBLESHOOTING.md          # Problem solving
│       └── scripts/                    # 6 powerful scripts
└── 🖼️ image-search/
    ├── .claude-plugin/plugin.json
    └── local-mcp/unsplash-mcp-server/  # MCP server
```

---

## 🛠️ Development

Want to contribute or create your own plugin? Here's how!

### Adding a New Plugin

1. **Create plugin directory:**

   ```bash
   mkdir -p my-plugin/.claude-plugin
   ```

2. **Add plugin.json:**

   ```json
   {
     "name": "my-plugin",
     "description": "What it does and when to use it",
     "version": "1.0.0",
     "author": { "name": "Your Name" }
   }
   ```

3. **Create SKILL.md or MCP server:**

   - For skills: Create `skills/my-skill/SKILL.md`
   - For MCP servers: Create `local-mcp/my-server/`

4. **Update marketplace.json:**
   ```json
   {
     "plugins": [
       {
         "name": "my-plugin",
         "source": "./my-plugin",
         "description": "Brief description"
       }
     ]
   }
   ```

### Best Practices

- ✅ **Progressive Disclosure** - Keep main docs concise, link to detailed references
- ✅ **Clear Descriptions** - Tell Claude WHEN to use your plugin
- ✅ **Examples First** - Show usage before explaining internals
- ✅ **Test Thoroughly** - Try multiple conversation styles
- ✅ **Document Everything** - Future you will thank present you!

---

## 🐛 Troubleshooting

### Common Issues

**Plugin Not Found:**

- Check `.claude-plugin/plugin.json` exists
- Verify path in `marketplace.json`
- Restart Claude Code

**Authentication Errors:**

- Verify API keys are set as environment variables
- Check credentials haven't expired
- Review plugin-specific auth docs

**Script Not Running:**

- Ensure dependencies are installed (`npm install` or `pip install`)
- Check Node.js/Python versions
- Review script-specific troubleshooting guides

### Getting Help

1. 📖 Check plugin-specific documentation
2. 🔍 Review TROUBLESHOOTING.md files
3. 🐛 Check GitHub issues
4. 💬 Reach out to plugin maintainers

---

## 🎨 Philosophy

This marketplace is built on three principles:

1. **🗣️ Natural Language First** - Talk to Claude like a human, not a CLI
2. **⚡ Speed Matters** - Caching, optimization, and smart defaults
3. **📖 Documentation as Love** - Clear guides make everyone's life better

---

## 📊 Stats

- **Total Plugins:** 10 (all ready to use!)
- **Languages:** TypeScript, Python, Shell
- **Protocols:** MCP, Skills, Scripts
- **Lines of Code:** 3000+ (and counting!)
- **Tokens Consumed:** 🪙🪙🪙🪙🪙 (too many to count)

---

## 🙏 Credits

### Built With

- **Claude Code** by Anthropic - The amazing AI coding assistant
- **MCP** - Model Context Protocol for extensibility
- **Monarch Money** - Personal finance management
- **Unsplash** - Beautiful free images

### Inspiration

Built for developers and power users who want to:

- Automate tedious tasks ⚡
- Work smarter, not harder 🧠
- Have fun with AI 🎉

---

## 📝 License

Each plugin maintains its own license. Check individual plugin directories for details.

---

### Ideas?

Have an idea for a plugin? Found a bug? Want to contribute?

This marketplace is always evolving! 🌱

---

## 💫 Fun Facts

- 🎯 The Monarch Money plugin can split receipts in under 2 seconds
- 🖼️ Image Search has access to over 3 million photos
- ⚡ Category caching makes repeat operations 10x faster
- 📝 Combined documentation exceeds 5000 words
- 🎪 This README contains 27+ emojis bringing joy to every section!

---

<div align="center">

### ⭐ Made with AI & ❤️ by David Asaf

_"The best tools are the ones you build yourself!"_

</div>

---

**Happy Coding! 🎉**
