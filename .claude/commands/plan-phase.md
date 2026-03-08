---
description: Start a new build phase. Orchestrator reads CLAUDE.md + SPEC.md, breaks the phase into tasks, writes them to postbox/todo.md, and queues agents.
---

Read CLAUDE.md and SPEC.md completely.

Then use the orchestrator subagent to plan $ARGUMENTS.

The orchestrator should:
1. Identify every file that needs to be built for this phase (from SPEC.md Section 14)
2. Write each file as a separate numbered task in postbox/todo.md using the exact task format
3. Order tasks by dependency (nothing depends on a file that doesn't exist yet)
4. Return a summary of: how many tasks queued, which agent handles each, and what the first task is

After the orchestrator finishes, tell me the plan and ask: "Ready to start Task 1?"
