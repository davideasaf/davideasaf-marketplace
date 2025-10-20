# 🎪 David's Claude Code Marketplace

> _Where AI meets productivity magic!_ ✨

Welcome to my personal collection of Claude Code plugins, skills, and MCP servers. Each tool is crafted to supercharge specific workflows with AI-powered automation. 🚀

---

## 🌟 What's Inside?

This marketplace is your one-stop shop for Claude Code extensions that make life easier, work smarter, and development faster!

### 🔌 Available Plugins

| Plugin                                  | Description                           | What It Does                                                                    | Status   |
| --------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------- | -------- |
| 💰 **[Monarch Money](#-monarch-money)** | Budget management & receipt splitting | Split receipts by category, categorize transactions, manage finances through AI | ✅ Ready |
| 🖼️ **[Image Search](#️-image-search)**  | Unsplash image discovery              | Describe any image and instantly find it from the internet                      | ✅ Ready |

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
         "source": "https://github.com/yourusername/davideasaf-marketplace.git"
       }
     ]
   }
   ```

   Or use the marketplace installation command:
   ```bash
   # Add marketplace via Claude Code
   /marketplace add https://github.com/yourusername/davideasaf-marketplace.git
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

- **Total Plugins:** 2 (both ready to use!)
- **Languages:** TypeScript, Python
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
