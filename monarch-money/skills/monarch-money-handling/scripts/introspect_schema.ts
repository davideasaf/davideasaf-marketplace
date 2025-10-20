#!/usr/bin/env tsx
/**
 * Introspect the Monarch Money GraphQL schema to find available mutations.
 */

import * as process from 'node:process';
import { MonarchClient } from 'monarchmoney';

async function introspectSchema(mm: MonarchClient) {
  // Standard GraphQL introspection query
  const introspectionQuery = `
    query IntrospectionQuery {
      __schema {
        mutationType {
          name
          fields {
            name
            description
            args {
              name
              type {
                name
                kind
                ofType {
                  name
                  kind
                }
              }
            }
          }
        }
      }
    }
  `;

  const result = await mm['graphql'].query(introspectionQuery);
  return result;
}

async function main() {
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });

  const email = process.env.MONARCH_EMAIL;
  const password = process.env.MONARCH_PASSWORD;

  if (!email || !password) {
    console.error('Error: Email and password required via env vars');
    process.exit(1);
  }

  try {
    await mm.login({ email, password, useSavedSession: true, saveSession: true });
  } catch (error) {
    console.error('Error logging in:', error);
    process.exit(1);
  }

  try {
    const schema = await introspectSchema(mm);
    console.log(JSON.stringify(schema, null, 2));
  } catch (error) {
    console.error('Error introspecting schema:', error);
    process.exit(1);
  }
}

main();
