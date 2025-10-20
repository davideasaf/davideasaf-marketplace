#!/usr/bin/env tsx
/**
 * Add or update notes on a Monarch Money transaction.
 *
 * Usage:
 *   tsx scripts/add_notes.ts <transaction_id> "Your note text here"
 *   tsx scripts/add_notes.ts <transaction_id> --clear  # Remove notes
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface AddNotesArgs {
  clear?: boolean;
  email?: string;
  password?: string;
}

async function addNotes(
  mm: MonarchClient,
  transactionId: string,
  notes: string
) {
  // Use the actual browser mutation instead of the SDK's outdated one
  const mutation = `
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

  const variables = {
    selectedTransactionIds: [transactionId],
    excludedTransactionIds: [],
    allSelected: false,
    expectedAffectedTransactionCount: 1,
    updates: { notes },
    filters: { transactionVisibility: 'non_hidden_transactions_only' },
  };

  const result = await mm['graphql'].mutation(mutation, variables);

  if (!result.bulkUpdateTransactions.success || result.bulkUpdateTransactions.errors?.length > 0) {
    throw new Error(`Failed to update notes: ${JSON.stringify(result.bulkUpdateTransactions.errors)}`);
  }

  return result.bulkUpdateTransactions;
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      clear: { type: 'boolean', default: false },
      email: { type: 'string' },
      password: { type: 'string' },
    },
    allowPositionals: true,
  });

  const args = values as AddNotesArgs;

  // Get transaction ID and notes from positional arguments
  if (positionals.length === 0) {
    console.error('Error: Transaction ID required as first argument');
    process.exit(1);
  }

  const transactionId = positionals[0];

  // Determine note text
  let noteText: string;
  if (args.clear) {
    noteText = '';
  } else if (positionals.length < 2) {
    console.error('Error: Must provide note text or use --clear');
    process.exit(1);
  } else {
    noteText = positionals[1];
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

  // Add notes
  try {
    const result = await addNotes(mm, transactionId, noteText);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Error adding notes:', error);
    process.exit(1);
  }
}

main();
