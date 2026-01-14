# Linear API Reference

Quick reference for Linear's GraphQL API patterns used in linear-dev-flow.

## API Endpoint

```
POST https://api.linear.app/graphql
```

## Authentication

```bash
# Header format
Authorization: lin_api_xxxxx
```

No "Bearer" prefix - just the API key directly.

## Common Queries

### Get Current User

```graphql
query {
  viewer {
    id
    name
    email
  }
}
```

### List Teams

```graphql
query {
  teams {
    nodes {
      id
      key
      name
    }
  }
}
```

### Get Workflow States for Team

```graphql
query($teamId: String!) {
  workflowStates(filter: { team: { id: { eq: $teamId } } }) {
    nodes {
      id
      name
      type
      position
    }
  }
}
```

State types:
- `backlog` - Backlog states
- `unstarted` - Not started (Todo, Dev Ready)
- `started` - In progress
- `completed` - Done states
- `canceled` - Canceled

### Get Issue by Identifier

```graphql
query($identifier: String!) {
  issue(id: $identifier) {
    id
    identifier
    title
    description
    priority
    priorityLabel
    state {
      id
      name
      type
    }
    assignee {
      id
      name
    }
    labels {
      nodes {
        id
        name
        color
      }
    }
    comments {
      nodes {
        id
        body
        createdAt
        user {
          name
        }
      }
    }
    createdAt
    updatedAt
    url
  }
}
```

### List Issues by State

```graphql
query($teamId: String!, $stateName: String!) {
  issues(
    filter: {
      team: { id: { eq: $teamId } }
      state: { name: { eqIgnoreCase: $stateName } }
    }
    first: 50
    orderBy: priority
  ) {
    nodes {
      id
      identifier
      title
      priority
      priorityLabel
      state {
        id
        name
      }
      createdAt
      url
    }
  }
}
```

## Common Mutations

### Create Comment

```graphql
mutation($issueId: String!, $body: String!) {
  commentCreate(input: {
    issueId: $issueId
    body: $body
  }) {
    success
    comment {
      id
      body
      createdAt
    }
  }
}
```

### Update Issue State

```graphql
mutation($issueId: String!, $stateId: String!) {
  issueUpdate(id: $issueId, input: {
    stateId: $stateId
  }) {
    success
    issue {
      id
      identifier
      state {
        name
      }
    }
  }
}
```

### Update Issue Assignee

```graphql
mutation($issueId: String!, $assigneeId: String!) {
  issueUpdate(id: $issueId, input: {
    assigneeId: $assigneeId
  }) {
    success
    issue {
      id
      assignee {
        name
      }
    }
  }
}
```

## Priority Values

| Priority | Value | Label |
|----------|-------|-------|
| No Priority | 0 | None |
| Urgent | 1 | Urgent |
| High | 2 | High |
| Medium | 3 | Medium |
| Low | 4 | Low |

## Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `{ id: { eq: "xxx" } }` |
| `neq` | Not equals | `{ id: { neq: "xxx" } }` |
| `in` | In array | `{ id: { in: ["a", "b"] } }` |
| `nin` | Not in array | `{ id: { nin: ["a", "b"] } }` |
| `eqIgnoreCase` | Case-insensitive equals | `{ name: { eqIgnoreCase: "todo" } }` |
| `contains` | Contains substring | `{ title: { contains: "bug" } }` |
| `containsIgnoreCase` | Case-insensitive contains | `{ title: { containsIgnoreCase: "bug" } }` |

## Pagination

Linear uses cursor-based pagination:

```graphql
query {
  issues(first: 50, after: "cursor_value") {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      id
      title
    }
  }
}
```

## Rate Limits

- **Standard limit:** 1500 requests per hour per API key
- **Complexity limit:** Query complexity score (larger queries cost more)

Best practices:
- Batch multiple fields in single queries
- Use filters to limit results
- Cache responses when possible

## Error Handling

Errors are returned in the `errors` array:

```json
{
  "errors": [
    {
      "message": "Entity not found",
      "extensions": {
        "code": "NOT_FOUND"
      }
    }
  ],
  "data": null
}
```

Common error codes:
- `NOT_FOUND` - Entity doesn't exist
- `FORBIDDEN` - No permission
- `INVALID_INPUT` - Bad input data
- `RATE_LIMITED` - Too many requests

## Webhook Events (Reference)

If setting up webhooks, these are relevant events:
- `Issue` - Issue created/updated/deleted
- `Comment` - Comment created/updated/deleted
- `IssueLabel` - Label added/removed from issue

Webhook payload includes:
- `action`: create, update, remove
- `data`: Entity data
- `url`: Entity URL in Linear
