# Monarch Money Scripts

Run these commands from the skill directory, the directory that contains `SKILL.md`.

The primary scripts use saved Monarch sessions when available and fall back to:

- `MONARCH_EMAIL`
- `MONARCH_PASSWORD`
- `MONARCH_MFA_SECRET`

Do not commit `.env`, `.cache`, saved sessions, exports, or scraped customer data.

## Current Commands

| Command | Purpose |
| --- | --- |
| `npm run find -- --id <transaction_id>` | Fetch one transaction by ID. |
| `npm run find -- --date YYYY-MM-DD --merchant "Merchant"` | Search transactions by date/merchant. |
| `npm run categories` | List cached category groups and categories. |
| `npm run categories -- --refresh` | Refresh category cache from Monarch. |
| `npm run validate -- --splits-file /tmp/splits.json --amount -40.91` | Validate split JSON before mutating Monarch. |
| `npm run split-receipt -- <transaction_id> --splits-file /tmp/splits.json` | Split a receipt and add itemized notes. |
| `npm run notes -- <transaction_id> $'Line 1\nLine 2'` | Add or replace transaction notes. |
| `npm run update -- <transaction_id> --category <category_id>` | Update transaction fields. |
| `npm run tags -- --list` | List transaction tags. |
| `npm run tags -- --add <transaction_id> --tags <tag_id>` | Add tag IDs to a transaction. |
| `npm run bulk-update -- --updates-file /tmp/updates.json` | Apply a batch update file. |
| `npm run batch-refunds -- --days 14` | Coordinate Amazon refund review. |
| `npm run amazon-scrape -- --headless` | Scrape Amazon refund transaction data. |
| `npm run amazon-scrape-items -- --headless` | Scrape Amazon refunds and item details. |
| `npm run benchmark` | Run the local performance benchmark. |

## Split JSON Shape

```json
[
  {
    "merchantName": "Walmart",
    "amount": -20.78,
    "categoryId": "223967675759308363",
    "notes": "Groceries:\n- Milk - $4.37\n- Eggs - $5.46\nTotal: $9.83"
  }
]
```

Use negative amounts for expenses. Split amounts must sum to the original transaction within one cent.

## Implementation Notes

Several high-use scripts call Monarch's web GraphQL API through `scripts/utils/monarch_graphql.ts` because the public SDK can drift behind the web app schema. If a GraphQL command fails with a schema error, inspect `.cache/graphql-failures/`, compare against the current Monarch web request, and patch the query or mutation before retrying mutations.
