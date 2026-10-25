# Project Atlas Employee Assistant — test cases

This is the complete test checklist for the **fictional** Project Atlas demo. The [README](README.md) explains the architecture and gives a short walkthrough. This document covers normal flows, boundaries, failures, and the evidence to inspect. A listed case is **not** automatically tested merely because it appears here; the last section identifies the automated checks already in `tests/`.

## How to run this guide

1. **Understand the setup.** Use the Sydney AWS profile and the S3 bucket, Bedrock Knowledge Base, two DynamoDB tables, and AgentCore Memory described in [README setup](README.md#set-up-aws-resources). These services hold different state, so a missing variable can stop the page before a request is sent. The local `.env.local` holds only AgentCore resource IDs and is Git-ignored.
2. **Start the app.** From the repository folder in VS Code's terminal, activate `.venv`, load the local AgentCore IDs, and start Streamlit. The command below selects the existing demo services. A successful start prints a local Streamlit URL; the page title is **Project Atlas Employee Assistant**.

   ```bash
   source .venv/bin/activate
   source .env.local
   AWS_PROFILE=aws-learning-lab \
   BEDROCK_KNOWLEDGE_BASE_ID=KGBNAPZGM8 \
   ATLAS_SOURCE_BUCKET=sghanige-atlas-knowledge-20261024-4827 \
   ATLAS_ACTIONS_TABLE=project-atlas-actions \
   ATLAS_MEMORY_TABLE=project-atlas-memory \
   python -m streamlit run app.py
   ```

   The AWS profile selects credentials; the other variables tell each Python client which demo resource to use. If the AWS login expired, run `aws login --profile aws-learning-lab --region ap-southeast-2` first. Never paste credentials into the app or Git.
3. **Establish a baseline.** The fictional status document is version 2, dated **24 October 2026**. Its open actions are IT sign-in testing due **27 October**, Workplace Operations approval due **28 October**, and Product Operations support-route testing due **29 October**. The existing IT task may already be in DynamoDB, so a repeated task request should normally return **created = false**. Do not delete the shared task just to force a first-create result.
4. **Record evidence.** For each case, record Pass/Fail/Not run, the observed text or screenshot, the conversation ID, and any AWS error. Under **What internally happened**, expand the applicable **Step details** to inspect retrieved passages, prompt blocks, cache usage, and tool results. Under **Observability**, compare the values to the expectations below. Model wording can vary; verify facts, source references, and actions rather than exact prose.

### Test sequence and cost

Run **A1–A3, B1, C1, D1, E1–E2, G1, H1, I1** first for a short smoke test. Then work through the remaining cases. Model questions, RAG, AgentCore requests, and task-tool requests use AWS services and may incur charges. Direct preference commands, fact inspection, and the offline unit suite do not invoke Nova. Use the same fictional users throughout. Never change the live S3 status or delete a live DynamoDB table for a negative test; use mocks or a separate temporary fixture resource.

**Result key:** UI = live Streamlit check; API = read-only or controlled local API check; Offline = mocked unit/integration check; Isolated = use a disposable fixture or mocked service. “N/A” means the app cannot measure that property for the request; it does not mean zero.

## A. Setup and page state

| ID | Mode | Steps | Expected result |
| --- | --- | --- | --- |
| A1 | UI | Open the local Streamlit URL. | Page title, fictional user selector, **Your request**, and **Send** appear. No AWS credentials appear on the page. |
| A2 | UI | With AgentCore variables set, select Alex. Record the displayed conversation ID. Refresh the same URL. | The conversation ID remains in the URL and is shown again. Previous saved turns for that ID can reload. A browser refresh may reset browser-session observability rates. |
| A3 | UI | Switch to Taylor, then back to Alex. | The two users have separate conversation IDs and memory. The selector is explicitly labelled as a demo control, not authentication. |
| A4 | UI | Click **New conversation** for Alex. | Alex gets a new conversation ID. The prior conversation is not deleted; its URL is needed to revisit it. Taylor's ID is unchanged. |
| A5 | UI | Send an empty or whitespace-only request. | Warning asks for a request. No RAG or model call occurs. **What internally happened** and Observability show a rejected transaction. |
| A6 | Isolated | Start without `ATLAS_AGENTCORE_MEMORY_ID`, with the other required variables set. | Page explains that conversation history is not configured; existing RAG/task paths remain usable. Restore the variable afterward. |
| A7 | Isolated | Start without `ATLAS_MEMORY_TABLE`. | Page reports personal memory unavailable and stops before accepting requests. Restore the variable; do not treat this as a model failure. |
| A8 | Offline | Run `python -m unittest discover -s tests -q` inside `.venv`. | Suite ends with `OK`. This checks mocked behavior only; it does not prove that current AWS resources are reachable. |

## B. RAG and project facts

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| B1 | UI | `What remains outstanding before the Project Atlas pilot can launch?` | Answer identifies all three open actions, owners, and exact dates; says pilot is not ready. The current status document appears in Sources. No internal task is created. |
| B2 | UI | Expand **What internally happened** after B1. | Retrieval step shows passage text, source URI and score; prompt step shows those passages in the ConverseStream request. Source references such as `[1]` correspond to numbered returned passages. |
| B3 | UI | `What is the Project Atlas kickoff plan?` | Answer uses the kickoff document for meeting facts and cites it. It does not infer that the pilot has launched. |
| B4 | UI | `Does the approved draft mean Workplace Operations has approved the Sydney office information?` | Answer distinguishes a draft from approval and reports the current status as pending. |
| B5 | UI | `If the IT sign-in due date passes, can we assume the work is complete?` | Answer does not infer completion from a due date; it uses the latest explicit status. This check remains relevant after 27 October 2026. |
| B6 | UI | `Who is Project Atlas's chief financial officer?` | If the corpus does not name one, the assistant says the documents do not provide that fact. A made-up person is a failure. |
| B7 | API | Run `AWS_PROFILE=aws-learning-lab BEDROCK_KNOWLEDGE_BASE_ID=KGBNAPZGM8 python rag_client.py` from the activated venv. | Printed hits have S3 source URIs and excerpts. This checks retrieval separately from answer generation. |
| B8 | Isolated | Mock Knowledge Base Retrieve to return no hits, then call `run_agent`. | Request stops with `No Project Atlas sources were retrieved.` No task is written. Do not delete the live KB to create this condition. |
| B9 | Isolated | Provide a newer dated status fixture in a mock S3 response, leaving the live bucket untouched. Separately provide the newer passage as a mock KB retrieval hit. | `load_latest_status` and task selection use the newer S3 status. The answer uses the newer passage only when KB retrieval supplies it; an S3 update alone does not refresh the KB. Older episodes are historical only. |

## C. Response preference in DynamoDB

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| C1 | UI | Select Alex; if needed click **Forget saved preference**. Send `What do you remember about me?` | Reports no saved response preference. The saved-preferences block is absent; no model or KB call is needed. |
| C2 | UI | `Remember that I prefer short updates with blockers, owners, and due dates.` | Saves **Brief bullets with blockers, owners, and due dates** for Alex immediately; no separate Save button or model call. |
| C3 | UI | Ask B1 with Alex's brief style. | Answer uses concise action bullets with owners, dates and citations. Flow identifies **Brief action bullets (saved preference)**. Project facts are unchanged. |
| C4 | UI | With Taylor, send `Remember that I prefer detailed explanations.`; ask B1. | Taylor gets a detailed format; Alex's brief style remains separate. |
| C5 | UI | Stop Streamlit, restart it, and inspect both users. | Saved styles persist because DynamoDB holds them. |
| C6 | UI | Send `Forget my response preference` as text. | Application denies deletion and directs the user to the **Forget saved preference** button. Existing style remains. |
| C7 | UI | Click **Forget saved preference** for Alex. | Alex's saved style disappears; Taylor's style remains. Repeating B1 uses **Default prose (no saved preference)**. |
| C8 | UI | Send an unsupported style, such as `Remember that I prefer rhyming answers.` | App gives a controlled-format validation error; it does not save arbitrary instructions. |
| C9 | Offline | Compare Bedrock prompt blocks for a saved style and no style. | Source context and cache checkpoint precede the format directive. Clearing a preference cannot leave it inside a reused cached prefix. |

## D. Automatic personal-fact learning in DynamoDB

Personal-fact learning is **on by default** but intentionally narrow: it accepts explicit first-person statements for the demo teams **IT**, **Product Operations**, **Workplace Operations**, and the roles **Project Atlas coordinator**, **IT tester**, **pilot volunteer**. It does not extract arbitrary personal information.

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| D1 | UI | With Alex, send `I work on the IT team. What remains outstanding for Project Atlas?` | **Personal facts learned for Alex Morgan** immediately shows **Team: IT**. Flow and Memory level report a newly learned fact. Current project facts still come from RAG. |
| D2 | UI | Send `What do you remember about me?` | Direct memory response shows `team = IT` and any saved response style. No KB or model call is required. |
| D3 | UI | With Taylor, send `I am a pilot volunteer. What remains outstanding?` | Taylor shows **Role: pilot volunteer**; Alex's Team fact is not copied. |
| D4 | UI | With Taylor, before saving any team fact for Taylor, send `Who works on the IT team?` | This question alone does not save a personal fact or establish Taylor's team. An answer based solely on the question must not claim Taylor belongs to IT. |
| D5 | UI | With Alex, send `I work on the Workplace Operations team. What remains outstanding?` | Alex's `fact#team` value updates to **Workplace Operations**; the previous Team value is replaced, not duplicated. |
| D6 | UI | Click **Forget team fact** for Alex. | The saved DynamoDB Team fact disappears. Taylor's Role fact remains. The original sentence can still exist in AgentCore conversation history for its retention period; this button does not erase that raw event. |
| D7 | UI | Ask a question without an explicit first-person team/role statement, for example `Is the IT team testing sign-in?` | No new personal fact is saved. Talking *about* a team is not declaring membership. |
| D8 | Offline | Run `extract_personal_facts` tests for clear first-person statements and questions about other people. | Supported statements produce controlled `team`/`role` values; questions and unsupported statements produce no fact. |
| D9 | UI | Restart the app after D1 or D3, before deleting the fact. | Saved fact remains because DynamoDB stores it. Clean up with the relevant Forget button after testing. |

## E. Conversation history in AgentCore Memory

Only the **model question and task paths** currently write USER/ASSISTANT/TOOL events to AgentCore. Direct response-style commands, memory inspection, denied text deletion, and empty submissions bypass the model path and do not create conversation events. The model loads at most the eight most recent turns, although the resource keeps raw events for seven days.

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| E1 | UI | Click **New conversation** for Alex. Ask B1, then ask `Which of those actions is due on 28 October?` | Second request loads prior turns, expands its short retrieval query with the previous question, and identifies Workplace Operations approval due 28 October. |
| E2 | UI | Refresh the same conversation URL after E1. | **Conversation history** lists saved USER and ASSISTANT events in order. The first request's events are visible on the next page rerun or refresh. |
| E3 | UI | Ask at least five question/answer pairs in one conversation, then refresh. | History shown to the model and in the page is capped at the latest eight turns; older raw events may still be in AgentCore. |
| E4 | UI | Click **New conversation**; ask a short follow-up without supplying its referent. | New conversation loads zero previous turns. The assistant should not silently reuse the old session's raw chat context. Relevant episodes, if any, can still be retrieved separately. |
| E5 | UI | Switch from Alex to Taylor using the same browser. | Taylor does not see Alex's raw turns. Each AgentCore call uses the selected actor ID. |
| E6 | UI | Ask an informational question after a prior task request in the same conversation. | The prior TOOL outcome can appear as history, but it cannot authorize another task write. Only the current explicit create-task request can pass the Python guard. |
| E7 | Offline | Mock AgentCore `list_events` with out-of-order records. | `recent_turns` sorts them and returns the bounded chronological window. |
| E8 | Isolated | Mock AgentCore event-write failure after a model answer. | The answer remains available; metrics show `conversation_save_error` and do not claim the history was saved. |

## F. Episodic memory across conversations

AgentCore creates episodes asynchronously after it detects a completed interaction. A zero episode count immediately after a request is **inconclusive**. The strategy namespace is actor-scoped; past episodes must not be treated as current Project Atlas status.

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| F1 | UI | Ask for the next internal task in an Alex conversation. Start a new Alex conversation and ask `What happened when I requested the next Project Atlas task earlier?` | When AgentCore has generated and retrieved a relevant episode, **What internally happened** reports at least one episode and Step details show its ID/text. Answer identifies it as a remembered interaction, not a current-status source. |
| F2 | UI | Repeat F1 later if episode count is zero. | Zero remains an honest observation, not a fabricated memory. Record the elapsed time and retry; do not count the first zero as a failure of conversation saving. |
| F3 | UI | Ask F1's recollection question as Taylor. | Taylor cannot retrieve Alex's episode; namespace and actor isolation are maintained. |
| F4 | UI | After an episode about an old status exists, ask B1 again. | Current KB/S3 evidence takes precedence for current project state. Episode details may help explain past interactions only. |
| F5 | Offline | Mock episode retrieval and inspect the Bedrock request. | Episode text is after the cache checkpoint, marked reference-only, and paired with the selected actor namespace. |
| F6 | API | With the configured IDs, inspect **Memory level** after a request. | `episodes_loaded` is the number retrieved for that transaction. It is not a count of all episodes stored in AgentCore. |

## G. MCP task creation and status rules

The shared demo may already contain the IT task. Cases that require a **new** write or malformed/latest-status variations belong in isolated fixtures or mocks. Never modify the live status document just to force a failure.

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| G1 | UI | `Create an internal task for the next open Project Atlas action.` | Model selects the MCP task tool. Python checks the current request, MCP reads latest S3 status, and DynamoDB creates or returns the IT task. Page shows owner IT, due **2026-10-27**, state Open and S3 source. If the model does not select the tool, record a failure rather than claiming a task was created. |
| G2 | UI | Send G1 again. | **Existing task returned; no duplicate was created.** Task action ID and original `created_at` remain the same. |
| G3 | UI | Ask B1 without a create-task command. | No task tool call or DynamoDB task write, even if the answer mentions open actions. |
| G4 | UI | `What is the next task?` | Informational question only. It does not pass the explicit `create`/`please create` + `task` application guard. |
| G5 | Offline | Make the model request the task tool for a question that did not explicitly request creation. | Python raises `Task creation requires an explicit create-task request.` The MCP tool is not called. |
| G6 | Isolated | Run the action workflow against a fresh disposable task table. | First request has `created=True`; second has `created=False`. Both point to the same action ID. Delete the disposable table afterward; do not reset the shared demo table. |
| G7 | Isolated | Mock latest S3 status with no Open actions section, a malformed action line, a missing owner/date, or no status object. | Workflow fails with a clear parser/source error. No task item is created from incomplete facts. |
| G8 | Isolated | Mock a newer status with a different earliest-due open action. | Tool selects that action from the newer status, not the older KB passage or prior episode. |
| G9 | Offline | Mock the MCP tool raising an AWS error after model tool selection. | `AgentExecutionError` retains tool timing, retrieved sources and failed-stage data for Observability. Page must not report a created task. |
| G10 | UI | Inspect **Internal task** after G1 or G2. | “Created/returned” describes a tracker record only; it does not say the volunteer sign-in work is complete or that an email was sent. |

## H. Prompt caching and performance

Bedrock controls the server-side prompt cache. A cache write makes reuse possible; it is **not** a hit. A repeat can still miss because eligibility, source order/content, time, or Bedrock's cache behavior may differ.

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| H1 | UI | Ask B1, then repeat the identical question soon afterward with the same user/style and unchanged sources. | Compare cache-read and cache-write token counts. **Prompt cache hit** is shown only when cache-read tokens are positive; a hit is not guaranteed. |
| H2 | UI | Change Alex's response style and repeat B1. | Style changes are after the checkpoint. The new answer format applies even if the earlier source prefix is reused. |
| H3 | UI | Inspect **How this request ran** for an answer. | Shows backend time, KB retrieval time, Bedrock call time, TTFT from the local client to first nonempty text, input/output/cache tokens, and approximate post-first-text output rate. |
| H4 | UI | Inspect a task-only response. | **First tool event** is shown instead of answer TTFT. Approximate output-token rate may be N/A. |
| H5 | UI | Compare the same question after adding recent conversation turns. | History is after the checkpoint, so it may change uncached input while preserving the eligible source prefix. Do not compare raw total latency as a controlled cache experiment unless retrieved source order/content also match. |
| H6 | Offline | Feed stream metadata with cache write but zero cache read. | Flow says **cache write**, not **cache hit**; reuse percentage is zero. |
| H7 | Offline | Feed stream metadata with positive cache read. | Flow says **cache hit** and calculates reuse from uncached + cache-read + cache-write input tokens. |

## I. Observability and quality claims

| ID | Mode | Request or steps | Expected result |
| --- | --- | --- | --- |
| I1 | UI | After B1, expand **System level**, **RAG level**, **Answer level**, **Agent level**, **Memory level**, and **Session rates and resource use**. | All six groups appear. Measured fields have values; unsupported evaluations say N/A rather than invented scores. |
| I2 | UI | Inspect RAG level for exact B1 wording. | Returned passage list includes rank, URI, and Bedrock retrieval score. Recall@5 is calculated only against the small labelled demo document set for this exact question. |
| I3 | UI | Ask a different project question. | Recall@5 is N/A unless that exact question has labelled relevant documents. Retrieval score is not presented as Recall@5 or answer correctness. |
| I4 | UI | Inspect Answer level after a cited answer. | Citation-number check only verifies numbers are within returned-source range. Faithfulness, groundedness, answer relevance, context relevance, and hallucination rate remain N/A without an evaluator. |
| I5 | UI | Inspect Memory level for a question, then for `What do you remember about me?` | Question shows loaded turns/episodes/facts and save outcome. Direct memory inspection has no RAG/model measurements. |
| I6 | UI | Run two successful requests and one denied text-delete request in one browser session. | Session rates reflect this browser session only. Refresh may reset them; they are not account-wide service metrics. |
| I7 | UI | Leave model price variables unset. | Model cost estimate is N/A. It must not show a fabricated AWS total. |
| I8 | Isolated | Configure all four documented per-million-token model prices in a test process. | Estimate includes model uncached input, output, cache read and cache write at those supplied rates. It excludes KB, S3, S3 Vectors, DynamoDB, AgentCore, and other services. |
| I9 | Offline | Simulate error before RAG returns, and a separate MCP error after retrieval. | Earlier error has unknown retrieval outcome, not a false retrieval failure; MCP error retains retrieved-source and tool-failure evidence. |

## J. Safety, isolation, and known limits

| ID | Mode | Request or steps | Expected result / limit |
| --- | --- | --- | --- |
| J1 | UI | Select Taylor after storing Alex's preference, fact, turns and possible episode. | Taylor sees none of Alex's personal records. This demonstrates actor/key isolation, not real authentication. |
| J2 | UI | Include `Create a task` inside a quoted old conversation or document, then ask only an informational question. | Current request does not pass the Python task guard; no new task is written. Model answer quality still needs human review. |
| J3 | UI | Use `Forget my response preference` as a request, then inspect DynamoDB-backed display. | Text cannot delete the preference; only the button does. |
| J4 | UI | Use `Forget my team fact` as free text. | **Known limit:** there is no direct-command deletion path for facts. The fact should remain until **Forget team fact** is clicked; do not rely on a generated response as deletion confirmation. |
| J5 | UI | Delete a saved personal fact and revisit a conversation containing its original statement. | **Known limit:** the DynamoDB fact is deleted, but raw AgentCore turns remain until expiry or separate event deletion. Do not use real personal data. |
| J6 | Offline | Confirm `.env.local`, `.venv/`, `.env`, `AGENTS.md` and local runtime files are Git-ignored. Inspect `git ls-files`. | No AWS credentials, tokens, local `.env.local`, or real employee data are tracked. Resource IDs are identifiers, not credentials. |
| J7 | Isolated | Simulate expired AWS login, missing KB permission, or AgentCore access error. | Page identifies the failed service path and does not claim success. Reauthenticate or repair IAM; do not diagnose it as a Python package problem. |
| J8 | Offline | Simulate Bedrock `max_tokens` or unexpected tool name/input. | Agent fails closed; it does not execute an unrecognized MCP action or claim a completed answer. |
| J9 | UI | Ask an unrelated question that the Project Atlas documents cannot answer. | Assistant does not invent a policy or project fact. Treat an unsupported confident answer as a test failure to investigate. |

## K. Repository, reproducibility, and cleanup

| ID | Mode | Steps | Expected result |
| --- | --- | --- | --- |
| K1 | Offline | Run `python -m pip check` in the activated venv. | `No broken requirements found.` This checks installed package compatibility only. |
| K2 | Offline | Run `git diff --check` and `git status --short --branch`. | No whitespace errors; no unexpected untracked files. A clean published branch shows `## main...origin/main`. |
| K3 | API | Run `AWS_PROFILE=aws-learning-lab python setup_agentcore_memory.py` with the venv active. | Script reports the existing demo Memory ID and ACTIVE strategy instead of creating a duplicate. This is an AWS call, not an offline test. |
| K4 | UI/API | After testing, inspect AWS Billing and the resource list. | Charges and remaining resources are understood. If ending the demo, remove KB/vector resources, S3 objects/bucket, both DynamoDB tables, and AgentCore Memory deliberately; deleting one resource does not guarantee removal of its dependencies. |

## Automated coverage versus manual coverage

Run the current automated suite with:

```bash
python -m unittest discover -s tests -q
```

The suite currently covers mocked model streaming and cache metadata; response-style parsing, persistence and isolation; UI request-flow rendering; basic personal-fact extraction; AgentCore event ordering, actor namespace and tool-event shape; citation/Recall@5 reporting; and mocked task-tool success/failure guards. It does **not** automatically execute every case above. In particular, live Bedrock answer quality, eventual episode extraction, fresh-task creation in a disposable DynamoDB table, malformed S3 status permutations, real IAM failure handling, privacy deletion of raw events, and cost verification need the manual or isolated checks identified in the tables.

| Automated test file | Cases it partly supports | What still needs the live or isolated check |
| --- | --- | --- |
| `tests/test_agent_client.py` | B1, C9, G2, G5, G9, H1 | Real model choice, AWS retrieval, task writes and cache hits. |
| `tests/test_app_memory.py` | C2, C5, C6, I5 | Browser rendering and persistence in the real DynamoDB table. |
| `tests/test_memory_client.py` | C2, C4, C6, C8, D5 | Real table behavior and full page flow. |
| `tests/test_conversation_memory.py` | D1, D4, E7, F3 | Real AgentCore writes, expiration and asynchronous episode generation. |
| `tests/test_request_flow.py` | B2, G2, H6, H7 | Values reported by the live Bedrock request. |
| `tests/test_observability.py` | I2, I4, I7, I8, I9 | Actual answer quality and billed AWS cost. |

These mappings mean **related unit coverage**, not that a UI case passes automatically. Record the result of each live case separately.

For a repeatable evidence log, copy this small table under your test run notes rather than changing the test cases themselves:

| Run date | Case ID | Result (Pass / Fail / Not run) | Evidence or observed output | Issue link / follow-up |
| --- | --- | --- | --- | --- |
| | | | | |
