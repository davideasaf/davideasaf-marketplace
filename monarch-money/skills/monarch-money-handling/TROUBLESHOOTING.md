# Troubleshooting

## Authentication

If a script cannot authenticate:

1. Confirm a saved Monarch session exists or set `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and, when needed, `MONARCH_MFA_SECRET`.
2. Confirm the same credentials work in the Monarch web app.
3. Never print secret values while debugging.

## GraphQL Errors

Errors such as HTTP `400`, missing fields, or unexpected GraphQL validation failures usually mean Monarch's web API drifted.

1. Check `.cache/graphql-failures/` for the saved operation, variables, response text, and query hash.
2. Perform the same action in the Monarch web app.
3. Compare browser GraphQL traffic against the script.
4. Patch the operation name, variables, selected fields, or mutation input shape.
5. Run a read-only command before retrying a mutation.

## Category Cache

If categories are missing or stale:

```bash
npm run categories -- --refresh
```

The cache is stored under `.cache/` and should not be committed.

## Split Validation

Before splitting receipts:

```bash
npm run validate -- --splits-file /tmp/splits.json --amount -40.91
```

Common failures:

- Split amounts do not sum to the source transaction.
- A split is missing `merchantName`, `amount`, or `categoryId`.
- A category ID is stale or does not exist.
- Notes are missing from a split that should be itemized.

## Shell Quoting

When notes contain newlines or dollar signs, prefer single-quoted ANSI-C shell strings:

```bash
npm run notes -- <transaction_id> $'Groceries:\n- Milk - $4.37'
```

If the shell strips dollar amounts, quote the note differently or place the data in a JSON file.

## Safe Mutation Practice

- Read the transaction first with `npm run find -- --id <transaction_id>`.
- Confirm amount, merchant, account, and current category.
- Mutate one representative row first when testing a new query or workflow.
- Avoid bulk updates unless the update set is deterministic and reviewed.
