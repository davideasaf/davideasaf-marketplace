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
import { monarchGraphQL, printGraphQLError } from './utils/monarch_graphql';

interface AddNotesArgs {
  clear?: boolean;
}

async function addNotes(
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

  const result = await monarchGraphQL<{
    bulkUpdateTransactions: {
      success: boolean;
      affectedCount: number;
      errors?: Array<{ message: string }>;
      __typename?: string;
    };
  }>('Common_BulkUpdateTransactionsMutation', mutation, variables);

  if (!result.bulkUpdateTransactions.success || (result.bulkUpdateTransactions.errors?.length ?? 0) > 0) {
    throw new Error(`Failed to update notes: ${JSON.stringify(result.bulkUpdateTransactions.errors)}`);
  }

  return result.bulkUpdateTransactions;
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      clear: { type: 'boolean', default: false },
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

  // Add notes
  try {
    const result = await addNotes(transactionId, noteText);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    printGraphQLError(error);
    process.exit(1);
  }
}

main();
