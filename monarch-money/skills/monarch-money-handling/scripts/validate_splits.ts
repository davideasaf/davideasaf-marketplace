#!/usr/bin/env tsx
/**
 * Validate transaction splits before executing.
 *
 * Usage:
 *   tsx scripts/validate_splits.ts --splits-file splits.json --amount -40.91
 *   tsx scripts/validate_splits.ts --splits-json '[...]' --amount -40.91
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as process from 'node:process';
import { parseArgs } from 'node:util';

interface TransactionSplit {
  merchantName: string;
  amount: number;
  categoryId: string;
  notes?: string;
}

interface ValidateSplitsArgs {
  'splits-json'?: string;
  'splits-file'?: string;
  amount?: number;
}

const CACHE_FILE = path.join(__dirname, '..', '.cache', 'categories.json');

interface Category {
  id: string;
  name: string;
  group?: { id: string; name: string; type: string };
}

interface CategoryGroup {
  id: string;
  name: string;
  type: string;
}

async function loadCategories(): Promise<{
  categories: Category[];
  categoryGroups: CategoryGroup[];
} | null> {
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

async function validateSplits(
  splits: TransactionSplit[],
  expectedAmount: number | undefined
) {
  const issues: string[] = [];
  const warnings: string[] = [];

  // Load categories for validation
  const categoryData = await loadCategories();

  // Validate each split
  for (let i = 0; i < splits.length; i++) {
    const split = splits[i];
    const prefix = `Split ${i + 1}`;

    // Check required fields
    if (!split.merchantName) {
      issues.push(`${prefix}: Missing merchantName`);
    }
    if (split.amount === undefined || split.amount === null) {
      issues.push(`${prefix}: Missing amount`);
    }
    if (!split.categoryId) {
      issues.push(`${prefix}: Missing categoryId`);
    }

    // Check amount is negative (expense)
    if (split.amount > 0) {
      warnings.push(`${prefix}: Amount is positive (${split.amount}). Expected negative for expense.`);
    }

    // Check category ID exists and is not Business
    if (categoryData && split.categoryId) {
      const category = categoryData.categories.find(c => c.id === split.categoryId);
      if (!category) {
        issues.push(`${prefix}: Category ID "${split.categoryId}" not found`);
      } else if (category.group?.type === 'business') {
        issues.push(
          `${prefix}: Category "${category.name}" is a Business category. Use personal categories for splits.`
        );
      }
    }

    // Check notes exist (recommended)
    if (!split.notes || split.notes.trim() === '') {
      warnings.push(`${prefix}: No notes provided. Consider adding itemized details.`);
    }
  }

  // Validate total
  if (splits.length > 0) {
    const total = splits.reduce((sum, s) => sum + s.amount, 0);
    const rounded = Math.round(total * 100) / 100;

    if (expectedAmount !== undefined) {
      const diff = Math.abs(rounded - expectedAmount);
      if (diff > 0.01) {
        issues.push(
          `Split amounts sum to ${rounded}, expected ${expectedAmount} (difference: ${diff.toFixed(2)})`
        );
      }
    }

    console.log(`\nSplit Summary:`);
    console.log(`  Total splits: ${splits.length}`);
    console.log(`  Sum of amounts: ${rounded}`);
    if (expectedAmount !== undefined) {
      console.log(`  Expected amount: ${expectedAmount}`);
      console.log(`  Difference: ${(rounded - expectedAmount).toFixed(2)}`);
    }
  }

  // Display results
  console.log('');
  if (issues.length === 0 && warnings.length === 0) {
    console.log('✅ All validations passed!');
    return true;
  }

  if (issues.length > 0) {
    console.log('❌ Issues found:');
    issues.forEach(issue => console.log(`   - ${issue}`));
  }

  if (warnings.length > 0) {
    console.log('\n⚠️  Warnings:');
    warnings.forEach(warning => console.log(`   - ${warning}`));
  }

  return issues.length === 0;
}

async function main() {
  const { values } = parseArgs({
    options: {
      'splits-json': { type: 'string' },
      'splits-file': { type: 'string' },
      amount: { type: 'string' },
    },
  });

  const args = values as any;

  // Parse splits
  let splits: TransactionSplit[] = [];

  if (args['splits-json']) {
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
    console.error('Error: Must provide --splits-json or --splits-file');
    process.exit(1);
  }

  // Parse expected amount
  const expectedAmount = args.amount ? parseFloat(args.amount) : undefined;

  // Validate
  const valid = await validateSplits(splits, expectedAmount);

  process.exit(valid ? 0 : 1);
}

main();
