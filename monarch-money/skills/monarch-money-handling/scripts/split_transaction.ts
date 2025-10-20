#!/usr/bin/env tsx
/**
 * Split a Monarch Money transaction into multiple categories.
 *
 * Usage:
 *   tsx scripts/split_transaction.ts <transaction_id> --splits-json '[{"merchantName": "Walmart Groceries", "amount": -50.00, "categoryId": "123"}, {"merchantName": "Walmart Household", "amount": -25.50, "categoryId": "456"}]'
 *   tsx scripts/split_transaction.ts <transaction_id> --splits-file splits.json
 *   tsx scripts/split_transaction.ts <transaction_id> --clear  # Remove all splits
 */

import * as fs from 'node:fs';
import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface TransactionSplit {
  merchantName: string;
  amount: number;
  categoryId: string;
  notes?: string;
}

interface SplitTransactionArgs {
  'splits-json'?: string;
  'splits-file'?: string;
  clear?: boolean;
  email?: string;
  password?: string;
}

async function splitTransaction(
  mm: MonarchClient,
  transactionId: string,
  splits: TransactionSplit[]
) {
  // Use the actual browser mutation instead of the SDK's outdated one
  const mutation = `
    mutation Common_SplitTransactionMutation($input: UpdateTransactionSplitMutationInput!) {
      updateTransactionSplit(input: $input) {
        errors {
          fieldErrors {
            field
            messages
            __typename
          }
          message
          code
          __typename
        }
        transaction {
          id
          hasSplitTransactions
          splitTransactions {
            id
            amount
            notes
            hideFromReports
            merchant {
              id
              name
              __typename
            }
            category {
              id
              name
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
    }
  `;

  // Transform splits to the format the API expects
  // Note: notes field is NOT supported in splits - it must be set separately per the API
  const splitData = splits.map(split => ({
    merchantName: split.merchantName,
    hideFromReports: false,
    amount: split.amount,
    categoryId: split.categoryId,
    ownerUserId: null,
  }));

  const variables = {
    input: {
      transactionId,
      splitData,
    },
  };

  const result = await mm['graphql'].mutation(mutation, variables);

  if (result.updateTransactionSplit.errors) {
    const errors = result.updateTransactionSplit.errors;
    throw new Error(`Split transaction failed: ${JSON.stringify(errors)}`);
  }

  const transaction = result.updateTransactionSplit.transaction;

  // Add notes to each split transaction if provided
  if (transaction.splitTransactions && splits.some(s => s.notes)) {
    const bulkUpdateMutation = `
      mutation Common_BulkUpdateTransactionsMutation(
        $selectedTransactionIds: [ID!]
        $excludedTransactionIds: [ID!]
        $allSelected: Boolean!
        $expectedAffectedTransactionCount: Int!
        $updates: TransactionUpdateParams!
        $filters: TransactionFilterInput
      ) {
        bulkUpdateTransactions(
          selectedTransactionIds: $selectedTransactionIds
          excludedTransactionIds: $excludedTransactionIds
          updates: $updates
          allSelected: $allSelected
          expectedAffectedTransactionCount: $expectedAffectedTransactionCount
          filters: $filters
        ) {
          success
          affectedCount
          errors {
            message
            __typename
          }
          __typename
        }
      }
    `;

    // Update each split with notes
    for (let i = 0; i < splits.length; i++) {
      if (splits[i].notes && transaction.splitTransactions[i]) {
        const splitId = transaction.splitTransactions[i].id;
        const notesResult = await mm['graphql'].mutation(bulkUpdateMutation, {
          selectedTransactionIds: [splitId],
          excludedTransactionIds: [],
          allSelected: false,
          expectedAffectedTransactionCount: 1,
          updates: { notes: splits[i].notes },
          filters: { transactionVisibility: 'non_hidden_transactions_only' },
        });

        if (!notesResult.bulkUpdateTransactions.success) {
          console.warn(`Warning: Failed to add notes to split ${i + 1}`);
        }
      }
    }
  }

  return transaction;
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      'splits-json': { type: 'string' },
      'splits-file': { type: 'string' },
      clear: { type: 'boolean', default: false },
      email: { type: 'string' },
      password: { type: 'string' },
    },
    allowPositionals: true,
  });

  const args = values as SplitTransactionArgs;

  // Get transaction ID from positional argument
  if (positionals.length === 0) {
    console.error('Error: Transaction ID required as first argument');
    process.exit(1);
  }

  const transactionId = positionals[0];

  // Parse splits
  let splits: TransactionSplit[] = [];

  if (args.clear) {
    splits = [];
  } else if (args['splits-json']) {
    try {
      splits = JSON.parse(args['splits-json']);
    } catch (error) {
      console.error('Error parsing splits JSON:', error);
      process.exit(1);
    }
  } else if (args['splits-file']) {
    try {
      const fileContent = fs.readFileSync(args['splits-file'], 'utf-8');
      splits = JSON.parse(fileContent);
    } catch (error) {
      console.error('Error reading splits file:', error);
      process.exit(1);
    }
  } else {
    console.error('Error: Must provide --splits-json, --splits-file, or --clear');
    process.exit(1);
  }

  // Validate split structure
  if (splits.length > 0) {
    const requiredKeys = new Set(['merchantName', 'amount', 'categoryId']);
    for (let i = 0; i < splits.length; i++) {
      const split = splits[i] as any;
      const splitKeys = new Set(Object.keys(split));
      const missing = [...requiredKeys].filter((k) => !splitKeys.has(k));

      if (missing.length > 0) {
        console.error(`Error: Split ${i} missing required keys: ${missing.join(', ')}`);
        process.exit(1);
      }
    }
  }

  // Initialize Monarch Money
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });

  // Login
  const email = args.email || process.env.MONARCH_EMAIL;
  const password = args.password || process.env.MONARCH_PASSWORD;

  if (!email || !password) {
    console.error('Error: Email and password required (via args or env vars)');
    process.exit(1);
  }

  try {
    await mm.login({ email, password, useSavedSession: true, saveSession: true });
  } catch (error) {
    console.error('Error logging in:', error);
    process.exit(1);
  }

  // Split transaction
  try {
    const result = await splitTransaction(mm, transactionId, splits);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Error splitting transaction:', error);
    process.exit(1);
  }
}

main();
