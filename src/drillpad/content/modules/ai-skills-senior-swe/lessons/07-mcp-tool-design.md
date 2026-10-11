# MCP (Model Context Protocol): Designing Tools Agents Can Use

## Why This Matters in Interviews

MCP is becoming the standard for "how do you let an agent access your systems." Companies building internal tools, AI infrastructure, or AI-adjacent products are asking "can you design an MCP server for X?" It's the difference between "I know agents exist" and "I know how to build systems agents actually use."

## What MCP Actually Is

**Model Context Protocol** = a standard way for an LLM application to discover and call external tools/resources, **decoupled from any specific model provider.**

Before MCP: Every tool integration was custom
- Claude Code had its own way to call tools
- OpenAI had a different function-calling schema
- Cursor did it differently
- No one could reuse integrations

After MCP: Write a tool once, every MCP-compatible client (Claude Code, Cursor, Cline, etc.) can use it with zero additional work.

## The Architecture (Know This Cold)

```
Client (Claude Code, Cursor, agent framework)
    ↓
MCP Protocol (JSON-RPC over stdio, HTTP, or SSE)
    ↓
MCP Server (your tool)
    ↓
Backend (database, API, filesystem, etc.)

The server exposes three things:
  1. Tools — actions the agent can invoke
  2. Resources — data the agent can read (read-only, addressable)
  3. Prompts — reusable prompt templates
```

## Interview Pattern: Design an MCP Server

```
Q: "Design an MCP server for our internal ticketing system.
   Users should be able to create, search, and update tickets via agent."

Strong answer (signals you understand the domain):

  "Three parts:
  
  1. TOOLS (actions the agent takes)
     - search_tickets(query, status, assigned_to)
       Description: 'Search tickets by keyword and filter. Use when user
       asks about existing issues, bugs, feature requests.'
     - create_ticket(title, description, priority, assignee)
       Description: 'Create a new ticket. Only if user explicitly requests
       a new issue be created. Do not assume.'
     - update_ticket(ticket_id, status, comment)
       Description: 'Update ticket status or add comment.'
  
  2. RESOURCES (data agent can read without calling a tool)
     - tickets/{id} — individual ticket details (read-only)
     - statuses/ — list of valid ticket statuses
     - team-members/ — assignable people
     
     Why resources vs tools: ticket details don't *change* anything, so
     they're read-only context the agent can fetch without side effects.
  
  3. PROMPTS (optional reusable templates)
     - ticket-summary: 'Summarize this ticket for a developer'
     - create-bug-report: 'Template for a good bug report'
  
  Tool design specifics:
    - Descriptions matter more than I thought. This one sentence tells
      the agent WHEN to call the tool: 'Use when user asks about...'
      Not just WHAT it does.
    - search_tickets returns structured results, not a 50KB JSON dump.
      Filter/format server-side. Agent shouldn't burn context on noise.
    - All tools return errors the agent can act on. 'Ticket not found:
      did you mean ticket #123?' not 'ERROR' or null.
  
  Auth/credentials:
    - Never put secrets in tool parameters.
    - Route credentials through environment variables or a vault.
    - The agent never sees the actual API key.
  
  Versioning:
    - Once deployed, changing tool signatures breaks agents using it.
    - New parameters should be optional; changing return format is a
      breaking change (requires new tool or new version).
  
  Testing:
    - Test tools directly (not through an agent) first.
    - Verify the tool description is accurate (agents make wrong choices
      if descriptions are misleading).
    - A tool that works fine when called manually but confuses the agent
      is usually a description problem."

Why this signals good judgment:
  - You separated tools (side-effects), resources (read-only), and prompts
  - You thought about when the agent SHOULD call each tool
  - You didn't just dump all data into tools
  - You thought about credentials and versioning (production thinking)
  - You didn't forget error handling
```

## The Tool Description Trap

Most engineers write tool descriptions like:
```
"search_tickets: Search the ticket system"
```

The agent then:
- Can't tell if this is for finding existing issues or creating new ones
- Doesn't know whether to call it first or after trying something else
- Might use it for tasks where a human approval gate would be safer

Better description:
```
"search_tickets: Find existing tickets by keyword, status, or assignee.
Use this when the user asks about bugs, feature requests, or specific issues.
Do NOT use to check if a ticket exists before creating one — the agent should
attempt creation and handle 'duplicate' errors if returned."
```

**Rule:** if the agent could call your tool wrong, your description isn't precise enough.

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---|---|---|
| Tool description doesn't say WHEN to use it | Agent guesses, often wrong | "Use this when user asks about X" or "Use only after Y succeeds" |
| Tool returns 50KB unfiltered dump | Burns context, agent can't find signal | Return filtered results, top 10, just the ID, whatever agent actually needs |
| Tool has no error handling | Agent can't recover | Return structured errors: `{"error": "not found", "suggestion": "did you mean..."}` |
| Secrets in tool parameters | Credentials leak, agent mishandles them | Route secrets through env vars, tool parameter only gets scoped key name |
| Tool can do two things | Agent picks wrong one half the time | Split into two tools with precise names and descriptions |

## When MCP vs. Custom Integration

**Use MCP if:**
- Multiple agents/tools might call this (reusability matters)
- You're building infrastructure teams will rely on
- The tool is substantial enough to version and maintain

**Custom API is fine if:**
- Only one internal tool needs it
- It's temporary/prototype
- The cost of standardization isn't justified

## What This Signals in Interviews

- You understand tool-agent boundaries (what's a tool vs. what's context)
- You've thought about production (error handling, versioning, credentials)
- You can design interfaces agents actually use (not just APIs for humans)
- You know the emerging standard (MCP matters in AI-infra/systems roles)

In AI-infra interviews specifically, this is table-stakes: "Can you design a tool an agent can call reliably?" is the fundamental building block of any agentic system.
