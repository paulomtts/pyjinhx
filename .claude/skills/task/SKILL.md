---
name: task
description: Use when the user says "/task <issue#>" or asks to pick up / work / implement a subtask card from the v2 board — runs the task workflow (explore, spec+plan, adversarial validation, TDD implementation, review, tests, PR) end to end.
---

# /task — subtask workflow entry point

All pipeline logic lives in `.claude/workflows/task.js`. This skill is only the invocation shim.

Call the Workflow tool with `name: "task"` and `args: {"issue": <N>}`, where `<N>` is the issue number the user gave. The workflow itself validates the issue is `subtask`-labeled, moves the Project 12 board card through its stages (via its own Haiku-model board stages — no hook involved), and stops after opening the PR. It never merges; report the PR URL back to the user when it finishes.
