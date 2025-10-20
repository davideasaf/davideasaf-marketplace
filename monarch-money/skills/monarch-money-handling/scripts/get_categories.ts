#!/usr/bin/env tsx
/**
 * Get all transaction categories from Monarch Money.
 *
 * Usage:
 *   tsx scripts/get_categories.ts                    # Use cache if available
 *   tsx scripts/get_categories.ts --refresh          # Force refresh from API
 *   tsx scripts/get_categories.ts --format json      # JSON output
 *   tsx scripts/get_categories.ts --format list      # Human-readable list
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface GetCategoriesArgs {
  format?: string;
  refresh?: boolean;
  email?: string;
  password?: string;
}

const CACHE_DIR = path.join(__dirname, '..', '.cache');
const CACHE_FILE = path.join(CACHE_DIR, 'categories.json');

async function getCategories(mm: MonarchClient) {
  // Use the actual browser query that works
  const browserQuery = `
    query ManageGetCategoryGroups {
      categoryGroups {
        id
        name
        order
        type
        __typename
      }
      categories(includeDisabledSystemCategories: true) {
        id
        name
        order
        icon
        isSystemCategory
        systemCategory
        isDisabled
        group {
          id
          type
          name
          __typename
        }
        __typename
      }
    }
  `;

  const result = await mm['graphql'].query(browserQuery);

  return {
    categories: result.categories,
    categoryGroups: result.categoryGroups,
  };
}

interface Category {
  id: string;
  name: string;
  icon?: string;
  group?: { id: string; name: string; type: string };
}

interface CategoryGroup {
  id: string;
  name: string;
  type: string;
}

function formatCategoriesList(data: {
  categories: Category[];
  categoryGroups: CategoryGroup[];
}): string {
  const output: string[] = [];
  output.push('=== CATEGORY GROUPS ===\n');

  // Create a map of groups by ID
  const groupsMap = new Map(
    data.categoryGroups.map((g) => [g.id, g])
  );

  // Process each group
  for (const [groupId, group] of groupsMap) {
    output.push(`${group.name} (ID: ${group.id})`);

    // Find categories in this group
    const groupCategories = data.categories.filter(
      (c) => c.group?.id === groupId
    );

    for (const cat of groupCategories) {
      output.push(`  - ${cat.name} (ID: ${cat.id})`);
    }

    output.push('');
  }

  // Categories without a group
  const noGroup = data.categories.filter((c) => !c.group);
  if (noGroup.length > 0) {
    output.push('=== UNGROUPED CATEGORIES ===\n');
    for (const cat of noGroup) {
      output.push(`  - ${cat.name} (ID: ${cat.id})`);
    }
  }

  return output.join('\n');
}

async function loadCache(): Promise<{ categories: any[]; categoryGroups: any[] } | null> {
  try {
    if (!fs.existsSync(CACHE_FILE)) {
      return null;
    }
    const content = fs.readFileSync(CACHE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

async function saveCache(data: { categories: any[]; categoryGroups: any[] }) {
  try {
    if (!fs.existsSync(CACHE_DIR)) {
      fs.mkdirSync(CACHE_DIR, { recursive: true });
    }
    fs.writeFileSync(CACHE_FILE, JSON.stringify(data, null, 2));
  } catch (error) {
    console.error('Warning: Failed to save cache:', error);
  }
}

async function main() {
  const { values } = parseArgs({
    options: {
      format: { type: 'string', default: 'list' },
      refresh: { type: 'boolean', default: false },
      email: { type: 'string' },
      password: { type: 'string' },
    },
  });

  const args = values as GetCategoriesArgs;

  // Validate format
  if (args.format && !['json', 'list'].includes(args.format)) {
    console.error('Error: format must be "json" or "list"');
    process.exit(1);
  }

  let data: { categories: any[]; categoryGroups: any[] } | null = null;

  // Try to use cache unless refresh is requested
  if (!args.refresh) {
    data = await loadCache();
    if (data) {
      console.error('[Cache] Using cached categories');
    }
  }

  // Fetch from API if no cache or refresh requested
  if (!data) {
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

    // Get categories from API
    try {
      data = await getCategories(mm);
      await saveCache(data);
      console.error('[API] Fetched categories from Monarch Money');
    } catch (error) {
      console.error('Error getting categories:', error);
      process.exit(1);
    }
  }

  // Output
  try {
    if (args.format === 'json') {
      console.log(JSON.stringify(data, null, 2));
    } else {
      console.log(formatCategoriesList(data));
    }
  } catch (error) {
    console.error('Error formatting categories:', error);
    process.exit(1);
  }
}

main();
