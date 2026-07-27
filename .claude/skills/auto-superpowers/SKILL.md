---
name: auto-superpowers
description: Use when the user asks to run the superpowers workflow end-to-end with confirmation only at the initial requirements-alignment phase, and full automation through spec, plan, subagent execution, and finish.
---

# Auto Superpowers

Drive the full superpowers pipeline (brainstorm → spec → plan → subagent execution → finish) with **a single user checkpoint at the start**. After the user approves the aligned requirements, proceed without pausing until the branch is finished or a true blocker is reached.

**REQUIRED BACKGROUND:** You MUST understand `superpowers:using-superpowers`, `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:subagent-driven-development`, and `superpowers:finishing-a-development-branch` before using this skill. This skill orchestrates them; it does not redefine them.

## When to Use

- User says "auto", "自动化", "全自动", "一键跑完 superpowers", or asks to skip the spec/plan review gates
- User explicitly names this skill with `/auto-superpowers`
- User wants the superpowers discipline but only wants to be interrupted once (for alignment)

## When NOT to Use

- Task is trivial enough that brainstorming/spec is overkill — go straight to TDD
- User wants to drive each step themselves — use the individual superpowers skills
- Spec or plan requires human policy judgment the AI cannot make (legal, business, security review) — confirm before proceeding past brainstorming

## The Pipeline (in order)

```dot
digraph auto_superpowers {
    rankdir=TB;
    "Brainstorm with user" [shape=box];
    "User approves aligned requirements?" [shape=diamond];
    "STOP — user did not approve" [shape=box style=filled fillcolor=lightpink];
    "Write spec (brainstorm skill)" [shape=box];
    "Write plan (writing-plans skill)" [shape=box];
    "Subagent execution (subagent-driven-development)" [shape=box];
    "Final review clean?" [shape=diamond];
    "Finishing-a-development-branch" [shape=box style=filled fillcolor=lightgreen];

    "Brainstorm with user" -> "User approves aligned requirements?";
    "User approves aligned requirements?" -> "STOP — user did not approve" [label="no"];
    "User approves aligned requirements?" -> "Write spec (brainstorm skill)" [label="yes"];
    "Write spec (brainstorm skill)" -> "Write plan (writing-plans skill)";
    "Write plan (writing-plans skill)" -> "Subagent execution (subagent-driven-development)";
    "Subagent execution (subagent-driven-development)" -> "Final review clean?";
    "Final review clean?" -> "Finishing-a-development-branch" [label="yes"];
    "Final review clean?" -> "Subagent execution (subagent-driven-development)" [label="no — residual load-bearing findings"];
}
```

## Phase 1 — Brainstorm (the only checkpoint)

Invoke `superpowers:brainstorming`. Follow it exactly: explore project context, ask questions one at a time, present the design, write the spec doc, self-review it.

**Stop here. Present the aligned requirements to the user.** This is the *only* phase where confirmation is required.

Ask explicitly:
> "Requirements aligned. Spec draft is at `<path>`. Approve to proceed with auto-mode (plan → subagent execution → finish, no further checkpoints)?"

- **If approved** → continue to Phase 2 immediately, do not wait.
- **If changes requested** → revise the spec, ask again.
- **If declined** → stop. Do not run the rest of the pipeline.

**Critical:** This is the gate. Do not skip it. Do not ask the user to review the spec file path or any intermediate artifact — they will see the result, not the docs, in auto-mode.

## Phase 2 — Write Plan (auto-advance)

The user has approved. Invoke `superpowers:writing-plans`. Produce a detailed implementation plan with tasks, Global Constraints, file paths, and tests.

Do **not** ask the user to read or approve the plan. Continue to Phase 3.

If the writing-plans skill surfaces a conflict with the spec (e.g., a constraint that contradicts an earlier design decision), surface it to the user with both texts side-by-side and wait for resolution — this is a true blocker, not a checkpoint.

## Phase 3 — Subagent Execution (auto-advance)

Invoke `superpowers:subagent-driven-development`. Execute every task in the plan using fresh implementer subagents, task reviews, and the final whole-branch review.

Do **not** pause to ask "should I continue?" between tasks. The skill's normal "Continuous execution" rule applies — execute all tasks without stopping.

The only legitimate stop conditions during this phase:

1. **BLOCKED** status from an implementer that the controller cannot resolve (e.g., the plan itself is wrong).
2. **Load-bearing finding at the breaker cap** — adjudication surfaces a structural defect that downstream tasks would inherit.
3. **Spec/plan conflict** discovered mid-execution.

Any of the above → stop and report to user with: blocker description, relevant plan/spec text, and recommended next action.

Do not stop for: progress updates, "looking good so far" summaries, or non-load-bearing parked findings.

## Phase 4 — Finalize (auto-advance)

When the final whole-branch review is clean, invoke `superpowers:finishing-a-development-branch`. Present the branch state to the user.

The final whole-branch review happens inside Phase 3, not here. Phase 4 only handles integration decisions (merge / PR / keep working) — surface them in one message, do not ask serially.

## Rationalization Guards (DO NOT)

| Excuse | Reality |
|--------|---------|
| "Spec looks good, let me show the user before plan" | User asked for auto. Auto means auto. Continue. |
| "Plan is long, let me confirm before dispatching" | Plan is internal artifact. The user will see the result, not the plan. |
| "Task 1 is risky, let me check in" | Task review inside subagent-driven-development is the gate. Trust it. |
| "Final review found minors, let me ask user" | Park with rulings per subagent-driven-development. Continue. |
| "I'll just summarize progress" | Progress summaries are noise in auto-mode. The ledger carries the record. |
| "The user might want to change their mind" | They had the checkpoint. They approved. Honor the approval. |

## Red Flags — STOP and surface to user

- **Phase 1 alignment not approved** — never proceed past brainstorming
- **Spec/plan conflict discovered mid-execution** — present both texts, ask which governs
- **Implementer reports BLOCKED** on a non-mechanical issue (missing info, plan defect)
- **Load-bearing finding at the breaker cap** — structural failure that would propagate
- **Tests fail at the final whole-branch review** — stop, surface failures, ask before continuing

If none of those trigger, **continue silently**. No intermediate confirmation. No progress narration between phases. The ledger and git history carry the record.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Asking for confirmation after Phase 1 spec write | Phase 1 alignment *is* the checkpoint. Stop only there. |
| Treating "auto" as "skip brainstorming" | Brainstorming IS the alignment phase. It is included. |
| Letting the implementer subagent inherit session context | subagent-driven-development enforces fresh-context-per-task. Do not paste session history into dispatches. |
| Pausing at final-review residuals | Park minors with rulings per subagent-driven-development. Only stop on load-bearing findings. |
| Re-asking the user after they approved | If they said "go" at the alignment checkpoint, they meant "go all the way". |

## Quick Reference

| Phase | Skill to invoke | User confirmation? |
|-------|----------------|--------------------|
| 1. Brainstorm + alignment | `superpowers:brainstorming` | **YES — only checkpoint** |
| 2. Write plan | `superpowers:writing-plans` | No |
| 3. Execute | `superpowers:subagent-driven-development` | No (only on true blockers) |
| 4. Finalize | `superpowers:finishing-a-development-branch` | No (present options) |

## Invocation

```
/auto-superpowers <task description>
```

The skill reads the task description as the initial prompt for brainstorming. If no task description is given, ask the user what they want to build before invoking Phase 1.