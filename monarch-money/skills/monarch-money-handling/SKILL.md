---
name: Monarch Money Skills
description: Split receipts by category, categorize transactions, search Monarch Money transactions by date/merchant/amount, list budget categories, update transaction details, add itemized notes, and automate Amazon refund processing. Use when user provides receipt images, asks to split transactions, needs to find/categorize Monarch Money transactions, wants to update transaction metadata, or needs to process unreviewed Amazon refunds (starts with Monarch Money, pulls only needsReview=true transactions, scrapes Amazon for item details, updates with categories and notes).
---

# Monarch Money Skills

Split receipts, categorize transactions, and manage your Monarch Money budget through automated TypeScript scripts.

## When to Use This Skill

Claude will automatically invoke this skill when you:

- Provide a receipt image and want to split it by category
- Ask to find a specific transaction by date, merchant, or amount
- Need to categorize or recategorize Monarch Money transactions
- Want to add itemized notes to transactions
- Ask to list available budget categories
- Request updates to transaction details (merchant, amount, date, etc.)
- Want to process Amazon refunds (annotate with item details and categories)

**Just ask naturally** - Claude handles the complexity automatically.

---

## Invocation Examples

You can trigger this skill by saying things like:

- "Split this Walmart receipt into groceries and household items"
- "Find my Target transaction from October 16th"
- "What categories are available in Monarch Money?"
- "Add notes to this transaction with itemized prices"
- "Update the merchant name for transaction XYZ"
- "Categorize this $50 transaction as dining out"
- "Process my Amazon refunds from the past 14 days"

---

## Quick Start

**Most common use case:** Split a receipt by categories.

### User Experience

1. Say: "I have a Walmart receipt from Oct 16 I want to split"
2. Provide receipt image or transaction details
3. Claude will:
   - Find the transaction
   - Analyze receipt items
   - Get available categories
   - Create and validate splits
   - Execute with itemized notes

**That's it!** Claude handles all the script orchestration.

### Behind the Scenes (for Claude)

```bash
# 1. Find the transaction
npm run find -- --date 2025-10-16 --merchant "Walmart"

# 2. Get categories (uses cache by default - fast!)
npm run categories

# 3. Create splits.json with properly formatted notes
# Use format_notes.ts utilities for consistent formatting
cat > /tmp/splits.json << 'EOF'
[
  {
    "merchantName": "Walmart",
    "amount": -20.78,
    "categoryId": "223967675759308363",
    "notes": "Groceries:\n• Crackers - $3.88\n• Cottage cheese - $3.24\n• Milk - $4.37\n• Eggs - $5.46\nTotal: $17.95"
  },
  {
    "merchantName": "Walmart",
    "amount": -20.13,
    "categoryId": "223967675759308371",
    "notes": "Halloween:\n• Glow items - $9.84\n• Party supplies - $5.50\nTotal: $15.34"
  }
]
EOF

# 4. Validate splits (recommended - catches errors before API call)
npm run validate -- --splits-file /tmp/splits.json --amount=-40.91

# 5. Execute split with notes
npm run split-receipt -- <transaction_id> --splits-file /tmp/splits.json
```

**Critical Requirements:**
- ✅ Split amounts must sum to original transaction
- ✅ **ALWAYS include `notes` field** with newline-formatted bullet points
- ✅ Use `\n` for newlines in JSON, `$'...\n...'` in bash commands
- ✅ Use negative amounts for expenses (e.g., `--amount=-40.91`)
- ✅ Use `format_notes.ts` utilities for consistent formatting

**📖 See [FORMATTING_GUIDE.md](FORMATTING_GUIDE.md) for note formatting utilities**

---

## Core Workflows

### 1. Receipt Categorization (Primary)

**When:** User provides receipt image and wants items categorized.

**Scripts used:**
- `npm run find` - Locate the transaction
- `npm run categories` - Get category IDs (cached)
- `npm run validate` - Pre-flight validation
- `npm run split-receipt` - Execute split with notes

**Steps:**
1. Find transaction (by date + merchant or ID)
2. Analyze receipt and group items by category
3. Get category IDs (uses cache - instant)
4. Create splits JSON with itemized notes using `format_notes.ts` utilities
5. Validate splits (catches errors early)
6. Execute split (notes added automatically)

**Key Pattern:** Use newline formatting with bullet points:
```
Category:
• Item 1 - $14.99
• Item 2 - $8.99

Delivered: Oct 17
```

**📖 See [FORMATTING_GUIDE.md](FORMATTING_GUIDE.md) for formatting best practices**

### 2. Transaction Search

**When:** User needs to find specific transaction(s).

**Scripts used:**
- `npm run find` - Search transactions

**Common queries:**
```bash
# By date and merchant (most common)
npm run find -- --date 2025-10-16 --merchant "Walmart"

# By date range
npm run find -- --start-date 2025-10-01 --end-date 2025-10-31

# By ID (fastest - use when ID is known)
npm run find -- --id "224897271489997895"
```

**Performance tip:** Use `--id` when possible - it's 2-3x faster than date/merchant search.

### 3. Category Management

**When:** User asks about available categories or needs category IDs.

**Scripts used:**
- `npm run categories` - List categories (with caching)

```bash
# Human-readable list (uses cache - fast!)
npm run categories

# Force refresh from API
npm run categories -- --refresh
```

**Cache behavior:** First run fetches from API (~2-3s) and caches locally. Subsequent runs use cache (~0.5s, 5-6x faster). Only refresh when categories change.

### 4. Transaction Updates

**When:** User wants to update merchant, category, amount, or other fields.

**Scripts used:**
- `npm run update` - Update transaction fields
- `npm run notes` - Add/update notes only

```bash
# Update category
npm run update -- <id> --category <category_id>

# Update merchant
npm run update -- <id> --merchant "New Name"

# Multiple fields
npm run update -- <id> --category <cat_id> --merchant "Store" --notes "Note"

# Add notes with formatting (recommended)
npm run notes -- <id> $'Category:\n• Item 1 - $14.99\n• Item 2 - $8.99'
```

**Note formatting:** Always use `$'...\n...'` syntax for newlines in bash commands.

### 5. Amazon Refund Processing

**When:** User wants to annotate Amazon refund transactions with item details and correct categories.

**Workflow - START with Monarch Money:**
1. **Find unreviewed refunds in Monarch Money**
   - Filter: Amazon merchant, positive amounts (refunds), `needsReview: true`
   - Date range: Last 14 days (default) or custom range
2. **Scrape Amazon for item details**
   - **Recommended:** Use standalone Playwright scraper (outputs JSON, ~100 tokens)
   - Alternative: Use Playwright MCP (outputs ~15k tokens per call - inefficient)
3. **Update Monarch Money**
   - Infer categories from item names
   - Format notes with item details + order links
   - Bulk update transactions and mark as reviewed

**⚡ Standalone Amazon Scraper (Efficient):**
```bash
# First run - interactive login (opens browser)
npm run amazon-scrape

# Subsequent runs - headless with saved session
npm run amazon-scrape -- --headless > refunds.json

# With item details from order pages
npm run amazon-scrape-items -- --headless > refunds_with_items.json
```

Output format:
```json
{
  "refunds": [
    {
      "amount": 42.80,
      "date": "December 21, 2025",
      "orderNumber": "111-8140400-3904227",
      "orderUrl": "https://amazon.com/...",
      "items": [{ "name": "Balaclava Ski Mask", "price": 19.95 }]
    }
  ]
}
```

**Why use standalone scraper?**
- Playwright MCP returns ~15k tokens (full page state) per call
- Standalone scraper outputs ~100 tokens (JSON only)
- 150x more efficient for batch processing

**Critical:** Only process transactions with `reviewStatus: "needs_review"` - skip already reviewed refunds.

**Usage:**
```bash
# Process last 14 days (default)
npm run process-refunds

# Custom date range
npm run process-refunds -- --days 30
npm run process-refunds -- --start-date 2025-10-13 --end-date 2025-10-27

# Dry run (preview changes)
npm run process-refunds -- --days 14 --dry-run
```

**Note format:**
```
Refund: [Item Name from Amazon]
Order: https://www.amazon.com/gp/your-account/order-details?orderID=XXX
```

**Category Inference:**
The script automatically maps items to categories based on keywords:
- Phone case, charger → Electronics
- Clothing, shoes → Clothing
- Beauty products → Personal Care
- Art supplies, crafts → Hobbies
- Books → Books
- Food items → Groceries

**Performance:**
- Batch processing: 10 transactions/batch with 1s delay between batches
- Reuses single MonarchClient instance (avoids re-login overhead)
- Category lookup cached for speed
- ~2-3 seconds per transaction vs ~30s with individual `npm run notes` calls

**📖 For category mappings and performance details, see `scripts/process_amazon_refunds.ts`**

---

## Available Scripts

Quick reference of all scripts:

| Command | Purpose | Example |
|---------|---------|---------|
| `npm run find` | Search transactions | `npm run find -- --date 2025-10-16 --merchant "Walmart"` |
| `npm run categories` | List categories (cached) | `npm run categories` or `npm run categories -- --refresh` |
| `npm run validate` | Validate splits pre-flight | `npm run validate -- --splits-file splits.json --amount -40.91` |
| `npm run split-receipt` | Split + add notes (primary) | `npm run split-receipt -- <id> --splits-file splits.json` |
| `npm run notes` | Add/update notes only | `npm run notes -- <id> 'Note with $prices'` |
| `npm run update` | Update transaction fields | `npm run update -- <id> --category <cat_id>` |
| `npm run batch-refunds` | Find Amazon refunds (Phase 1) | `npm run batch-refunds -- --days 14` |
| `npm run finalize-refunds` | Update refunds with categories (Phase 3) | `npm run finalize-refunds` |
| `npm run amazon-scrape` | Standalone Amazon scraper (efficient) | `npm run amazon-scrape -- --headless` |
| `npm run amazon-scrape-items` | Scrape with item details | `npm run amazon-scrape-items -- --headless` |

**📖 For detailed script documentation and Amazon refund workflow, see [BATCH_REFUNDS_GUIDE.md](BATCH_REFUNDS_GUIDE.md)**

---

## Performance & Quality Features

### Category Caching
Categories are automatically cached locally (`.cache/categories.json`) for instant lookups. Only refreshed when explicitly requested.

**Why:** Categories rarely change, so caching avoids unnecessary API calls and speeds up workflows dramatically.

### Pre-flight Validation
Validate splits before executing to catch errors early:
- Check amounts sum correctly
- Verify category IDs are valid
- Warn about Business categories (cause errors)
- Ensure notes are present

**Why:** Catches mistakes before they hit the API, saving time and preventing bad data.

### Combined Operations
`split-receipt` combines splitting and notes in one operation for faster, atomic execution.

**Why:** Single API roundtrip ensures notes are always added with splits.

---

## Setup

### Prerequisites
- Node.js 18+
- Monarch Money account
- Environment variables configured

### Installation

```bash
cd /path/to/monarch-money-handling
npm install
```

### Authentication

Set environment variables:
```bash
export MONARCH_EMAIL="your-email@example.com"
export MONARCH_PASSWORD="your-password"
```

Or create `.env` file:
```
MONARCH_EMAIL=your-email@example.com
MONARCH_PASSWORD=your-password
```

### Security

- Credentials stored in environment variables or .env (never committed)
- Session tokens cached locally by SDK
- All API calls authenticated via Monarch Money GraphQL
- Review [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md) for API implementation details

### Test

```bash
npm run categories
```

Should list all your categories.

---

## Development Setup (monarchmoney-ts Library)

### Fork and Local Development

This skill uses a **locally linked fork** of the monarchmoney-ts library located at `./monarchmoney-ts` within this skill directory.

**Why a fork?**
- Enables local modifications when bugs are discovered
- Allows creating PRs back to the original repo
- Provides full control over the codebase
- Co-located with the skill for easier development

### Repository Links

- **Fork:** https://github.com/davideasaf/monarchmoney-ts
- **Upstream (Original):** https://github.com/keithah/monarchmoney-ts

### Making Changes to monarchmoney-ts

When you need to fix bugs or add features:

```bash
# 1. Navigate to the forked repo (co-located with skill)
cd monarchmoney-ts

# 2. Make your changes, then rebuild the library
npm run build

# 3. Test changes immediately in the skill (already linked via npm link)
cd ..
npm run categories  # or any other script

# 4. Commit and push to your fork
cd monarchmoney-ts
git add .
git commit -m "fix: description of fix"
git push origin main

# 5. Create PR to upstream via GitHub
# Visit: https://github.com/davideasaf/monarchmoney-ts
# Click "Contribute" → "Open pull request"
```

### Syncing with Upstream

Periodically sync your fork with the original repo:

```bash
cd monarchmoney-ts

# Fetch upstream changes
git fetch upstream

# Merge upstream into your fork
git merge upstream/main

# Push to your fork
git push origin main

# Rebuild to incorporate changes
npm run build
```

### Verifying the Link

Check that the skill is using your local fork:

```bash
npm list monarchmoney
# Should show: monarchmoney@1.1.3 -> ./monarchmoney-ts
```

---

## Common Patterns

### Pattern 1: Receipt with Mixed Categories

**Scenario:** Receipt has items from multiple categories (groceries, household, health).

**Approach:**
1. Group items by logical category
2. Calculate subtotals (include tax proportionally)
3. Verify subtotals sum to transaction total
4. Create splits with detailed itemized notes per category

### Pattern 2: Monthly Review

**Scenario:** Review and categorize all transactions for a month.

```bash
# Export monthly transactions
npm run find -- --start-date 2025-10-01 --end-date 2025-10-31 > monthly.json

# Review and categorize as needed
```

### Pattern 3: Batch Updates

**Scenario:** Update category for multiple related transactions.

```bash
for id in txn_123 txn_456 txn_789; do
  npm run update -- "$id" --category "new_category_id"
done
```

---

## Important Notes

### ⚠️ Dollar Signs in Notes

**Always use single quotes** when notes contain `$` symbols:

```bash
# ✅ Correct
npm run notes -- <id> 'Item $3.88, Item2 $5.99'

# ❌ Wrong - bash will expand variables
npm run notes -- <id> "Item $3.88, Item2 $5.99"
```

### ⚠️ Business Categories

Avoid Business categories (Postage & Shipping, Office Supplies) for splits. They cause cryptic API errors. Use General Shopping instead.

### ⚠️ Split Amount Sum

Splits must sum to original transaction amount (within $0.01 tolerance). Use `npm run validate` to check before executing.

---

## Troubleshooting

**Common issues:**
- Authentication failures → Check environment variables
- Dollar signs disappearing → Use single quotes
- Split amount mismatches → Use validation script
- Business category errors → Use General Shopping instead
- Transaction not found → Search by date/merchant

**📖 For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

---

## Technical Details

### GraphQL Implementation

The monarchmoney-ts SDK (v1.1.3) has outdated GraphQL queries. This skill uses actual working browser queries:

- `ManageGetCategoryGroups` - for categories
- `updateTransactionSplit` - for splits
- `bulkUpdateTransactions` - for notes

**📖 For technical details, see [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md)**

### Session Management

- Sessions cached locally by SDK (`useSavedSession: true`)
- Reduces login overhead
- First run requires full authentication

### Error Handling

All scripts follow consistent error handling:
- Exit code 0 = Success
- Exit code 1 = Error
- stdout = JSON results
- stderr = Error messages

---

## Performance Optimization

### Caching Strategy

- **Categories:** Cached locally after first fetch (~0.5s vs ~2-3s on subsequent calls)
- **Sessions:** Saved locally to avoid re-authentication overhead
- **Validation:** Local validation before API calls saves roundtrips

### Performance Tips for Claude

1. **Always use category cache** - Don't refresh unless user explicitly requests
2. **Find by ID when possible** - 2-3x faster than date/merchant search
3. **Use formatting utilities** - `format_notes.ts` provides consistent, optimized formatting
4. **Validate before executing** - Catch errors locally before API calls
5. **Batch operations** - Use `npm run update` once instead of multiple calls when updating same transaction
6. **Reuse MonarchClient instances** - For bulk operations, initialize once and reuse (avoids login overhead)
7. **Use batch scripts** - `npm run process-refunds` processes 10 transactions/batch vs individual `npm run notes` calls

### Why `npm run notes` Takes ~30s

**Root Causes:**
1. **Login overhead** - Each script call initializes new MonarchClient and authenticates (~5-10s)
2. **GraphQL queue management** - Request queueing/concurrency control adds latency
3. **Session validation** - Even with saved sessions, validation checks add overhead
4. **Single-transaction updates** - No batching optimization

**Solution:**
Use automated scripts like `npm run process-refunds` that:
- Initialize MonarchClient **once** and reuse for all updates
- Batch process transactions (10 at a time with 1s delays)
- Result: **~2-3 seconds per transaction** vs **~30s** per individual `npm run notes` call
- **10x+ performance improvement** for bulk operations

**📖 See [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) for detailed optimization strategies**

---

## Resources

### Documentation
- **Detailed Script Documentation:** [SCRIPTS_REFERENCE.md](SCRIPTS_REFERENCE.md)
- **Formatting Best Practices:** [FORMATTING_GUIDE.md](FORMATTING_GUIDE.md)
- **Performance Optimization:** [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)
- **Troubleshooting Guide:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Technical Details:** [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md)

### Repositories
- **Forked SDK (Local):** https://github.com/davideasaf/monarchmoney-ts (co-located at `./monarchmoney-ts`)
- **Upstream SDK:** https://github.com/keithah/monarchmoney-ts
- **Development Setup:** See "Development Setup (monarchmoney-ts Library)" section above

### External Links
- **Monarch Money:** https://www.monarchmoney.com

---

**Progressive disclosure:** Start with Quick Start, explore workflows as needed, reference detailed docs when troubleshooting.
