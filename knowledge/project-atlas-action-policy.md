# Project Atlas action-handling policy

Document version: 1
Effective date: 24 October 2026
Owner: Product Operations
Status: Fictional pilot policy

The Project Atlas employee assistant may turn an open project action into an internal task without waiting for a person to copy it into a tracker. It must base that task on the latest dated Project Atlas status update. A charter describes launch rules, and a kickoff note describes a meeting, but neither proves that an open action has been completed.

Before creating a task, the assistant must identify an explicit action, its responsible team, and its due date in the status update. It must record the source document and status date. If any of those fields is missing, the assistant should report that it cannot create a complete task from the available information. It must not invent an owner or deadline.

Each task record contains the project name, a concise action title, a description of the required work, the responsible team, the due date, the source document, the source status date, and the task state. A newly created task starts in the Open state. Creating a task is an internal tracking action; it does not send an email, contact an employee, or mark the underlying work complete.

The assistant should create at most one open task for the same Project Atlas action. If a matching open task already exists, it should return that task instead of creating a duplicate. A repeated request such as "create the next action" should therefore be safe to run twice. The assistant may report the task identifier so that a later request can refer to the same record.

A due date is a planning target, not evidence that work happened. Passing a due date must not change a task to Complete. Only a later dated status update that explicitly confirms completion may support that change. If the latest status still lists the action as open, the assistant must continue to describe it as open.

When asked whether the pilot can launch, the assistant must check the readiness conditions in the charter against the latest status update. It should identify unmet conditions and cite the documents used. It must not claim that a scheduled kickoff meeting, an approved draft, or a newly created task means the pilot is ready.

For a kickoff briefing, the assistant should summarize the pilot goal from the charter, the meeting plan from the kickoff note, and current blockers from the latest status update. It should keep recommendations separate from recorded project facts. If documents disagree, the assistant should show the conflict and prefer the latest explicit status for the current state of an action.