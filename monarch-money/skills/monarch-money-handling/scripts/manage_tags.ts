#!/usr/bin/env tsx
/**
 * Manage Monarch Money transaction tags.
 *
 * Usage:
 *   tsx scripts/manage_tags.ts --list
 *   tsx scripts/manage_tags.ts --create "Tulum Property" --color "#00A2C7"
 *   tsx scripts/manage_tags.ts --set <transaction_id> --tags <tag_id_1,tag_id_2>
 *   tsx scripts/manage_tags.ts --add <transaction_id> --tags <tag_id>
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { monarchGraphQL, printGraphQLError } from './utils/monarch_graphql';

interface TagArgs {
  list?: boolean;
  create?: string;
  color?: string;
  set?: string;
  add?: string;
  tags?: string;
  search?: string;
  limit?: string;
}

interface TransactionTag {
  id: string;
  name: string;
  color: string | null;
  order?: number | null;
  transactionCount?: number | null;
}

async function listTags(options: { search?: string; limit?: number } = {}) {
  const query = `
    query Common_GetHouseholdTransactionTags(
      $search: String
      $limit: Int
      $includeTransactionCount: Boolean = true
    ) {
      householdTransactionTags(search: $search, limit: $limit) {
        id
        name
        color
        order
        transactionCount @include(if: $includeTransactionCount)
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{ householdTransactionTags: TransactionTag[] }>(
    'Common_GetHouseholdTransactionTags',
    query,
    {
      search: options.search,
      limit: options.limit,
      includeTransactionCount: true,
    }
  );

  return result.householdTransactionTags;
}

async function createTag(name: string, color = '#00A2C7') {
  const mutation = `
    mutation Common_CreateTransactionTag($input: CreateTransactionTagInput!) {
      createTransactionTag(input: $input) {
        tag {
          id
          name
          color
          order
          transactionCount
          __typename
        }
        errors {
          message
          __typename
        }
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{
    createTransactionTag: {
      tag: TransactionTag | null;
      errors?: Array<{ message: string }> | null;
    };
  }>('Common_CreateTransactionTag', mutation, {
    input: {
      name,
      color,
    },
  });

  if (result.createTransactionTag.errors?.length || !result.createTransactionTag.tag) {
    throw new Error(`Failed to create tag: ${JSON.stringify(result.createTransactionTag.errors)}`);
  }

  return result.createTransactionTag.tag;
}

async function getTransactionTags(transactionId: string) {
  const query = `
    query GetTransactionDrawer($id: UUID!, $redirectPosted: Boolean) {
      getTransaction(id: $id, redirectPosted: $redirectPosted) {
        id
        tags {
          id
          name
          color
          order
          __typename
        }
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{
    getTransaction: {
      id: string;
      tags: TransactionTag[];
    };
  }>('GetTransactionDrawer', query, {
    id: transactionId,
    redirectPosted: true,
  });

  return result.getTransaction.tags || [];
}

async function setTransactionTags(transactionId: string, tagIds: string[]) {
  const mutation = `
    mutation Mobile_SetTransactionTagsRapidReview($input: SetTransactionTagsInput!) {
      setTransactionTags(input: $input) {
        errors {
          message
          code
          __typename
        }
        transaction {
          id
          tags {
            id
            name
            color
            order
            __typename
          }
          __typename
        }
        __typename
      }
    }
  `;

  const result = await monarchGraphQL<{
    setTransactionTags: {
      errors?: Array<{ message: string; code?: string }> | null;
      transaction: {
        id: string;
        tags: TransactionTag[];
      } | null;
    };
  }>('Mobile_SetTransactionTagsRapidReview', mutation, {
    input: {
      transactionId,
      tagIds,
    },
  });

  if (result.setTransactionTags.errors?.length || !result.setTransactionTags.transaction) {
    throw new Error(`Failed to set transaction tags: ${JSON.stringify(result.setTransactionTags.errors)}`);
  }

  return result.setTransactionTags.transaction;
}

function parseTagIds(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(',')
    .map((tagId) => tagId.trim())
    .filter(Boolean);
}

async function main() {
  const { values } = parseArgs({
    options: {
      list: { type: 'boolean', default: false },
      create: { type: 'string' },
      color: { type: 'string' },
      set: { type: 'string' },
      add: { type: 'string' },
      tags: { type: 'string' },
      search: { type: 'string' },
      limit: { type: 'string' },
    },
  });

  const args = values as TagArgs;

  try {
    if (args.list) {
      const tags = await listTags({
        search: args.search,
        limit: args.limit ? parseInt(args.limit, 10) : undefined,
      });
      console.log(JSON.stringify(tags, null, 2));
      return;
    }

    if (args.create) {
      const tag = await createTag(args.create, args.color);
      console.log(JSON.stringify(tag, null, 2));
      return;
    }

    if (args.set) {
      const tagIds = parseTagIds(args.tags);
      if (!tagIds.length) throw new Error('--tags is required for --set');
      const transaction = await setTransactionTags(args.set, tagIds);
      console.log(JSON.stringify(transaction, null, 2));
      return;
    }

    if (args.add) {
      const tagIds = parseTagIds(args.tags);
      if (!tagIds.length) throw new Error('--tags is required for --add');
      const existingTags = await getTransactionTags(args.add);
      const mergedTagIds = Array.from(new Set([...existingTags.map((tag) => tag.id), ...tagIds]));
      const transaction = await setTransactionTags(args.add, mergedTagIds);
      console.log(JSON.stringify(transaction, null, 2));
      return;
    }

    console.error('Error: provide --list, --create, --set, or --add');
    process.exit(1);
  } catch (error) {
    printGraphQLError(error);
    process.exit(1);
  }
}

main();
