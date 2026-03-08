---
description: Build the next open task from postbox/todo.md. Reads the task, invokes the right agent (gemini-coder/haiku-writer/react-builder), then runs python-reviewer on the result.
---

Read postbox/todo.md and find the first task with status OPEN.

Move it to IN PROGRESS.

Based on the **Agent** field in the task:
- If Agent is `gemini-coder` → use the gemini-coder subagent
- If Agent is `haiku-writer` → use the haiku-writer subagent  
- If Agent is `react-builder` → use the react-builder subagent

Pass the complete task details to the agent including:
- File path
- Spec section to read
- All requirements
- The test command

After the agent writes the file, move the task to NEEDS REVIEW.

Then use the python-reviewer subagent on the written file (skip for React/JS files — use haiku-writer's syntax check instead).

If review PASSES → move task to COMPLETED, run the test command, report result.
If review FAILS → report what needs to be fixed and ask me how to proceed.

Report: "Task [N] complete: [file]. Test: [PASS/FAIL]. Next open task: [task N+1]."
