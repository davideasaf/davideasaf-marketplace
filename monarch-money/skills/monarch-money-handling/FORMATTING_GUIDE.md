# Formatting Guide for Monarch Money Notes

This guide covers best practices for formatting transaction notes to maximize readability in Monarch Money.

## Key Discovery: Newlines Are Supported!

Monarch Money **fully supports newlines** in transaction notes, allowing for well-structured, readable itemized lists.

## Recommended Format

### For Single-Category Transactions

Use bullet points with newlines for easy scanning:

```
Category Name:
• Item 1 - $14.99
• Item 2 - $8.99
• Item 3 - $5.50

Delivered: Oct 17
Order: AMAZON-123456
```

**Benefits:**
- Easy to scan individual items
- Clear separation between items and metadata
- Professional appearance in the Monarch Money UI

### For Split Transactions

Each split should have its own itemized note:

```
Groceries:
• Crackers - $3.88
• Cottage cheese - $3.24
• Milk - $4.37
• Eggs - $5.46
Total: $17.95
```

```
Halloween:
• Glow sticks - $9.84
• Party supplies - $5.50
Total: $15.34
```

## Formatting Utilities

Use the provided formatting utilities in `scripts/utils/format_notes.ts`:

### formatReceiptNotes()

For complete receipt notes with optional metadata:

```typescript
import { formatReceiptNotes } from './utils/format_notes';

const notes = formatReceiptNotes({
  category: "Children's Clothing",
  items: [
    { name: "Purple leggings", price: 14.99 },
    { name: "Blue shirt", price: 8.99 }
  ],
  deliveryDate: "Oct 17",
  orderNumber: "AMAZON MKTPL*NM2237YZ0"
});
```

**Output:**
```
Children's Clothing:
• Purple leggings - $14.99
• Blue shirt - $8.99

Delivered: Oct 17
Order: AMAZON MKTPL*NM2237YZ0
```

### formatSplitNotes()

For individual splits in a multi-category transaction:

```typescript
import { formatSplitNotes } from './utils/format_notes';

const notes = formatSplitNotes("Groceries", [
  { name: "Crackers", price: 3.88 },
  { name: "Milk", price: 4.37 }
], true); // includeTotal
```

**Output:**
```
Groceries:
• Crackers - $3.88
• Milk - $4.37
Total: $8.25
```

### formatSimpleItemList()

For simple itemized lists without category headers:

```typescript
import { formatSimpleItemList } from './utils/format_notes';

const notes = formatSimpleItemList([
  { name: "Item 1", price: 14.99 },
  { name: "Item 2", price: 8.99 }
]);
```

**Output:**
```
• Item 1 - $14.99
• Item 2 - $8.99
```

## Shell Command Examples

### Using Newlines in Bash

Use `$'...'` syntax for newlines in bash commands:

```bash
npm run notes -- <id> $'Category:\n• Item 1 - $14.99\n• Item 2 - $8.99'
```

**Important:** Escape single quotes inside `$'...'`:

```bash
npm run notes -- <id> $'Children'\''s Clothing:\n• Item - $14.99'
```

### In JSON Files

For `splits.json`, use `\n` for newlines:

```json
[
  {
    "merchantName": "Walmart",
    "amount": -20.78,
    "categoryId": "223967675759308363",
    "notes": "Groceries:\n• Crackers - $3.88\n• Milk - $4.37\nTotal: $8.25"
  }
]
```

## Style Guidelines

### Bullet Points

**Use:** `•` (bullet character, U+2022)
**Not:** `-` or `*` (less visual weight)

### Price Format

**Use:** `$14.99` (currency symbol + 2 decimals)
**Not:** `14.99` or `$14.9` (missing context or precision)

### Spacing

- Single newline between items
- Blank line before metadata section
- No trailing newlines

### Category Headers

**Use:** `Category Name:` (title case + colon)
**Not:** `CATEGORY NAME` or `category name` (less readable)

## Before & After Examples

### Before (Old Format)

```
Groceries: Crackers $3.88, Cottage cheese $3.24, Milk $4.37, Eggs $5.46
```

**Problems:**
- Hard to scan individual items
- Prices blend into item names
- Long single line

### After (New Format)

```
Groceries:
• Crackers - $3.88
• Cottage cheese - $3.24
• Milk - $4.37
• Eggs - $5.46
Total: $12.95
```

**Benefits:**
- Each item on its own line
- Clear price separation with dashes
- Easy to verify totals
- Professional appearance

## Performance Considerations

### Newlines Don't Impact Performance

- API accepts newlines without issues
- No additional processing overhead
- Same number of API calls

### Best Practices

1. **Always use newlines** for multi-item notes
2. **Use formatting utilities** for consistency
3. **Test formatting** with a sample transaction first
4. **Include totals** for split transactions (helps verification)

## Claude Code Integration

When Claude processes receipts, it should:

1. Parse receipt items with prices
2. Group by category (if splitting)
3. Use `formatReceiptNotes()` or `formatSplitNotes()`
4. Generate properly formatted notes with newlines
5. Execute with `$'...\n...'` syntax in bash

Example workflow:
```bash
# 1. Claude analyzes receipt
# 2. Groups items by category
# 3. Generates formatted notes:

npm run notes -- <id> $'Children'\''s Clothing:\n• Purple leggings - $14.99\n• Blue shirt - $8.99\n\nDelivered: Oct 17'
```

## Future Improvements

Potential enhancements to consider:

1. **Auto-formatting script** - Reads existing notes and reformats with newlines
2. **Receipt parser** - OCR integration to extract items automatically
3. **Template library** - Pre-defined formats for common merchants
4. **Validation** - Warn if notes exceed character limits or lack structure

---

**Last Updated:** 2025-10-23
**Status:** Active - newlines confirmed working in production
