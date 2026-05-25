#!/usr/bin/env tsx
/**
 * Update a Monarch Money transaction (category, merchant, amount, date, etc.).
 *
 * Usage:
 *   tsx scripts/update_transaction.ts <transaction_id> --category <category_id>
 *   tsx scripts/update_transaction.ts <transaction_id> --merchant "New Merchant Name"
 *   tsx scripts/update_transaction.ts <transaction_id> --amount -123.45
 *   tsx scripts/update_transaction.ts <transaction_id> --date 2024-03-15
 *   tsx scripts/update_transaction.ts <transaction_id> --hide-from-reports true
 *   tsx scripts/update_transaction.ts <transaction_id> --needs-review false
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { monarchGraphQL, printGraphQLError } from './utils/monarch_graphql';

interface UpdateTransactionArgs {
  category?: string;
  merchant?: string;
  amount?: string;
  date?: string;
  'hide-from-reports'?: string;
  'needs-review'?: string;
  notes?: string;
}

async function updateTransaction(
  transactionId: string,
  updates: {
    category?: string;
    name?: string;
    amount?: number;
    date?: string;
    hideFromReports?: boolean;
    needsReview?: boolean;
    notes?: string;
  }
) {
  const mutation = `
    mutation Web_TransactionDrawerUpdateTransaction($input: UpdateTransactionMutationInput!) {
      updateTransaction(input: $input) {
        transaction {
          id
          amount
          pending
          date
          hideFromReports
          needsReview
          reviewedAt
          plaidName
          notes
          isRecurring
          category {
            id
            __typename
          }
          goal {
            id
            __typename
          }
          merchant {
            id
            name
            __typename
          }
          __typename
        }
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
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{
    updateTransaction: {
      transaction: unknown;
      errors?: {
        fieldErrors?: Array<{ field: string; messages: string[] }>;
        message?: string;
        code?: string;
      };
    };
  }>('Web_TransactionDrawerUpdateTransaction', mutation, {
    input: {
      id: transactionId,
      ...updates,
    },
  });

  if (result.updateTransaction.errors?.message || result.updateTransaction.errors?.fieldErrors?.length) {
    throw new Error(`Failed to update transaction: ${JSON.stringify(result.updateTransaction.errors)}`);
  }

  return result.updateTransaction.transaction;
}

function parseBoolean(value: string | undefined): boolean | undefined {
  if (value === undefined) return undefined;
  return value.toLowerCase() === 'true';
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      category: { type: 'string' },
      merchant: { type: 'string' },
      amount: { type: 'string' },
      date: { type: 'string' },
      'hide-from-reports': { type: 'string' },
      'needs-review': { type: 'string' },
      notes: { type: 'string' },
    },
    allowPositionals: true,
  });

  const args = values as UpdateTransactionArgs;

  // Get transaction ID from positional argument
  if (positionals.length === 0) {
    console.error('Error: Transaction ID required as first argument');
    process.exit(1);
  }

  const transactionId = positionals[0];

  // Build updates object
  const updates: any = {};

  if (args.category) updates.category = args.category;
  if (args.merchant) updates.name = args.merchant;
  if (args.amount) updates.amount = parseFloat(args.amount);
  if (args.date) updates.date = args.date;
  if (args['hide-from-reports'] !== undefined) {
    updates.hideFromReports = parseBoolean(args['hide-from-reports']);
  }
  if (args['needs-review'] !== undefined) {
    updates.needsReview = parseBoolean(args['needs-review']);
  }
  if (args.notes) updates.notes = args.notes;

  // Check if at least one field is being updated
  if (Object.keys(updates).length === 0) {
    console.error('Error: Must provide at least one field to update');
    process.exit(1);
  }

  // Update transaction
  try {
    const result = await updateTransaction(transactionId, updates);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    printGraphQLError(error);
    process.exit(1);
  }
}

main();
