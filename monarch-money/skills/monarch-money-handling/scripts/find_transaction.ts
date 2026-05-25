#!/usr/bin/env tsx
/**
 * Find a Monarch Money transaction by various criteria.
 *
 * Usage:
 *   tsx scripts/find_transaction.ts --id <transaction_id>
 *   tsx scripts/find_transaction.ts --date <date> --merchant <merchant_name>
 *   tsx scripts/find_transaction.ts --start-date <start> --end-date <end> --merchant <merchant>
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { monarchGraphQL, printGraphQLError } from './utils/monarch_graphql';

interface FindTransactionArgs {
  id?: string;
  date?: string;
  'start-date'?: string;
  'end-date'?: string;
  merchant?: string;
  limit?: string;
}

async function findTransactionById(transactionId: string) {
  const query = `
    query GetTransactionDrawer($id: UUID!, $redirectPosted: Boolean) {
      getTransaction(id: $id, redirectPosted: $redirectPosted) {
        id
        amount
        pending
        isRecurring
        date
        originalDate
        hideFromReports
        needsReview
        reviewedAt
        plaidName
        notes
        hasSplitTransactions
        isSplitTransaction
        isManual
        splitTransactions {
          id
          amount
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
        originalTransaction {
          id
          date
          amount
          merchant {
            id
            name
            __typename
          }
          __typename
        }
        attachments {
          id
          publicId
          extension
          sizeBytes
          filename
          originalAssetUrl
          __typename
        }
        account {
          id
          displayName
          logoUrl
          mask
          subtype {
            display
            __typename
          }
          __typename
        }
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
          transactionCount
          logoUrl
          recurringTransactionStream {
            id
            __typename
          }
          __typename
        }
        tags {
          id
          name
          color
          order
          __typename
        }
        needsReviewByUser {
          id
          __typename
        }
        __typename
      }
      myHousehold {
        users {
          id
          name
          __typename
        }
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{ getTransaction: unknown }>('GetTransactionDrawer', query, {
    id: transactionId,
    redirectPosted: true,
  });

  return result.getTransaction;
}

async function findTransactionsByCriteria(
  options: {
    startDate?: string;
    endDate?: string;
    merchant?: string;
    limit?: number;
  }
) {
  const query = `
    query Web_GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput, $orderBy: TransactionOrdering) {
      allTransactions(filters: $filters) {
        totalCount
        totalSelectableCount
        results(offset: $offset, limit: $limit, orderBy: $orderBy) {
          id
          amount
          pending
          date
          hideFromReports
          hiddenByAccount
          plaidName
          notes
          isRecurring
          reviewStatus
          needsReview
          isSplitTransaction
          dataProviderDescription
          attachments {
            id
            __typename
          }
          goal {
            id
            name
            __typename
          }
          category {
            id
            name
            icon
            group {
              id
              type
              __typename
            }
            __typename
          }
          merchant {
            name
            id
            transactionsCount
            logoUrl
            recurringTransactionStream {
              frequency
              isActive
              __typename
            }
            __typename
          }
          tags {
            id
            name
            color
            order
            __typename
          }
          account {
            id
            displayName
            icon
            logoUrl
            __typename
          }
          __typename
        }
        __typename
      }
      transactionRules {
        id
        __typename
      }
    }
  `;

  const filters: Record<string, unknown> = {
    transactionVisibility: 'non_hidden_transactions_only',
  };
  if (options.startDate) filters.startDate = options.startDate;
  if (options.endDate) filters.endDate = options.endDate;
  if (options.merchant) filters.search = options.merchant;

  const result = await monarchGraphQL<{
    allTransactions: {
      totalCount: number;
      totalSelectableCount: number;
      results: unknown[];
    };
  }>('Web_GetTransactionsList', query, {
    offset: 0,
    limit: options.limit || 100,
    filters,
    orderBy: 'date',
  });

  return result.allTransactions;
}

async function main() {
  const { values } = parseArgs({
    options: {
      id: { type: 'string' },
      date: { type: 'string' },
      'start-date': { type: 'string' },
      'end-date': { type: 'string' },
      merchant: { type: 'string' },
      limit: { type: 'string', default: '100' },
    },
  });

  const args = values as FindTransactionArgs;

  // Find transaction
  try {
    if (args.id) {
      // Find by ID
      const transaction = await findTransactionById(args.id);
      console.log(JSON.stringify(transaction, null, 2));
    } else {
      // Find by criteria
      const startDate = args['start-date'] || args.date;
      const endDate = args['end-date'] || args.date;

      if (!startDate) {
        console.error('Error: Must provide either --id or --date/--start-date');
        process.exit(1);
      }

      const transactionResult = await findTransactionsByCriteria({
        startDate,
        endDate,
        merchant: args.merchant,
        limit: args.limit ? parseInt(args.limit, 10) : 100,
      });

      console.log(
        JSON.stringify(
          {
            count: transactionResult.results.length,
            totalCount: transactionResult.totalCount,
            totalSelectableCount: transactionResult.totalSelectableCount,
            transactions: transactionResult.results,
          },
          null,
          2
        )
      );
    }
  } catch (error) {
    printGraphQLError(error);
    process.exit(1);
  }
}

main();
