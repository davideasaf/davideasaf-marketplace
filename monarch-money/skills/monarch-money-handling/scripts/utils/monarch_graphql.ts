import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { MonarchClient } from 'monarchmoney';

const API_BASE_URL = 'https://api.monarch.com';
const APP_ORIGIN = 'https://app.monarchmoney.com';
const DEFAULT_TIMEOUT_MS = 30000;
const SESSION_FILE = path.join(os.homedir(), '.mm', 'session.json');
const FAILURE_DIR = path.join(__dirname, '..', '..', '.cache', 'graphql-failures');

interface SessionData {
  token: string;
  createdAt?: number;
  expiresAt?: number;
  deviceUuid?: string;
}

export interface GraphQLFailureArtifact {
  operationName: string;
  queryHash: string;
  savedTo: string;
}

export class MonarchGraphQLError extends Error {
  status?: number;
  errors?: unknown[];
  artifact?: GraphQLFailureArtifact;

  constructor(message: string, options: { status?: number; errors?: unknown[]; artifact?: GraphQLFailureArtifact } = {}) {
    super(message);
    this.name = 'MonarchGraphQLError';
    this.status = options.status;
    this.errors = options.errors;
    this.artifact = options.artifact;
  }
}

function readSession(): SessionData | null {
  try {
    if (!fs.existsSync(SESSION_FILE)) return null;
    const session = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8')) as SessionData;
    if (!session.token) return null;
    if (session.expiresAt && Date.now() > session.expiresAt) return null;
    if (!session.expiresAt && session.createdAt && Date.now() - session.createdAt > 7 * 24 * 60 * 60 * 1000) return null;
    return session;
  } catch {
    return null;
  }
}

async function loginAndSaveSession(): Promise<SessionData> {
  const email = process.env.MONARCH_EMAIL;
  const password = process.env.MONARCH_PASSWORD;
  const mfaSecretKey = process.env.MONARCH_MFA_SECRET;

  if (!email || !password) {
    throw new Error('MONARCH_EMAIL and MONARCH_PASSWORD are required when no saved Monarch session exists');
  }

  const client = new MonarchClient({ baseURL: API_BASE_URL, logLevel: 'error' });
  await client.login({ email, password, mfaSecretKey, useSavedSession: true, saveSession: true });

  const session = readSession();
  if (!session) {
    throw new Error(`Monarch login completed but no usable session was found at ${SESSION_FILE}`);
  }
  return session;
}

export async function getSession(): Promise<SessionData> {
  return readSession() ?? loginAndSaveSession();
}

function headersForSession(session: SessionData): Record<string, string> {
  return {
    Accept: 'application/json',
    Authorization: `Token ${session.token}`,
    'Client-Platform': 'web',
    'Content-Type': 'application/json',
    Origin: APP_ORIGIN,
    'User-Agent':
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    'device-uuid': session.deviceUuid || 'unknown',
    'x-cio-client-platform': 'web',
    'x-cio-site-id': '2598be4aa410159198b2',
    'x-gist-user-anonymous': 'false',
  };
}

function queryHash(query: string): string {
  return crypto.createHash('sha256').update(query).digest('hex').slice(0, 12);
}

function saveFailureArtifact(input: {
  operationName: string;
  query: string;
  variables?: Record<string, unknown>;
  status?: number;
  responseText?: string;
  errors?: unknown[];
}): GraphQLFailureArtifact {
  fs.mkdirSync(FAILURE_DIR, { recursive: true });
  const hash = queryHash(input.query);
  const savedTo = path.join(
    FAILURE_DIR,
    `${new Date().toISOString().replace(/[:.]/g, '-')}-${input.operationName}-${hash}.json`
  );
  fs.writeFileSync(
    savedTo,
    JSON.stringify(
      {
        ...input,
        queryHash: hash,
        capturedAt: new Date().toISOString(),
        recoveryProtocol: [
          'Treat this as likely Monarch GraphQL drift if auth is valid.',
          'Open Monarch web app and perform the same action manually.',
          'Capture the working request from browser Network GraphQL traffic.',
          'Compare operation name, variables, required fields, and headers.',
          'Patch the script query/mutation to the browser-compatible shape.',
          'Rerun the failing script with read-only validation before mutating data.',
        ],
      },
      null,
      2
    )
  );
  return { operationName: input.operationName, queryHash: hash, savedTo };
}

export async function monarchGraphQL<T>(
  operationName: string,
  query: string,
  variables: Record<string, unknown> = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const session = await getSession();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let responseText = '';
  let status: number | undefined;
  try {
    const response = await fetch(`${API_BASE_URL}/graphql`, {
      method: 'POST',
      headers: headersForSession(session),
      body: JSON.stringify({
        query: query.trim(),
        variables,
        operationName: null,
      }),
      signal: controller.signal,
    });
    status = response.status;
    responseText = await response.text();

    let parsed: { data?: T; errors?: unknown[] };
    try {
      parsed = JSON.parse(responseText);
    } catch (error) {
      const artifact = saveFailureArtifact({ operationName, query, variables, status, responseText });
      throw new MonarchGraphQLError(`Monarch returned non-JSON for ${operationName}`, { status, artifact });
    }

    if (!response.ok || parsed.errors?.length || !parsed.data) {
      const artifact = saveFailureArtifact({
        operationName,
        query,
        variables,
        status,
        responseText,
        errors: parsed.errors,
      });
      const message = parsed.errors?.length
        ? `Monarch GraphQL error for ${operationName}: ${JSON.stringify(parsed.errors[0])}`
        : `Monarch HTTP ${status} for ${operationName}`;
      throw new MonarchGraphQLError(message, { status, errors: parsed.errors, artifact });
    }

    return parsed.data;
  } catch (error) {
    if (error instanceof MonarchGraphQLError) throw error;
    const artifact = saveFailureArtifact({
      operationName,
      query,
      variables,
      status,
      responseText,
      errors: [{ message: error instanceof Error ? error.message : String(error) }],
    });
    throw new MonarchGraphQLError(`Monarch request failed for ${operationName}: ${error}`, { status, artifact });
  } finally {
    clearTimeout(timeout);
  }
}

export function printGraphQLError(error: unknown): void {
  if (error instanceof MonarchGraphQLError) {
    console.error(error.message);
    if (error.artifact) {
      console.error(`GraphQL failure artifact: ${error.artifact.savedTo}`);
      console.error('Use the GraphQL drift self-heal protocol in SKILL.md before retrying mutations.');
    }
  } else {
    console.error(error);
  }
}
