# Chat-First Workflow and Resume Contract

Paper-Ear should feel like one continuous conversation, not a form builder or a command-line tutorial. Keep routine choices in the chat, persist them locally, pause once for voice listening, and resume from that exact point after the user replies.

## User-facing contract

1. Accept the paper and infer the requested output from the user's wording.
2. Ask at most one compact preference question for audience, focus, coverage, and language. Do not repeat anything the user already specified. If the user says “默认”, apply the documented defaults without another question.
3. Never ask the user to run a command, edit JSON, find a voice ID, or download a configuration file. Scripts and state files are agent-side implementation details.
4. For a video whose voices have not yet been approved, generate the local audition page and make this the one routine hard pause. Give the user a clickable `index.html`, ask them to listen, and request a reply such as `女声 D，男声 B` in the same chat.
5. End that turn while the state is `awaiting_voice_choice`. Do not pretend to keep rendering the full video in the background.
6. On the next user message, load `workflow_state.json` before asking any question. If the reply contains a valid pair, record it, create `voice_casting.json`, and continue through scripting, internal preview QA, full rendering, verification, and delivery.
7. After a valid voice choice, do not pause for routine storyboard or preview approval. Surface a new question only for a genuine blocker or a choice that materially changes scope, cost, privacy, or authority.

Web-only runs do not need the voice pause. If the same voice pair has already been explicitly approved for the current run, reuse it and continue.

## State machine

| State | Meaning | Next action |
|---|---|---|
| `preparing` | Source and chat preferences are recorded locally. | Inspect the paper and prepare requested outputs. |
| `awaiting_voice_choice` | The audition link has been delivered. | Stop the turn and wait for the user's male/female choice. |
| `running` | A valid voice pair is recorded. | Finish every requested artifact and run internal QA without routine pauses. |
| `blocked` | A real missing input, permission, dependency, or material decision prevents progress. | Ask only for the missing item. |
| `complete` | All requested artifacts passed their release gates. | Deliver clickable outputs and summarize limits. |

Do not use `blocked` for normal processing time or a failed first attempt that can be repaired locally.

## Persist the run locally

Initialize the run immediately after resolving the source and requested mode:

```bash
python <SKILL_DIR>/scripts/manage_run_state.py init \
  --state <run_dir>/workflow_state.json \
  --source-pdf /absolute/path/to/paper.pdf \
  --output-mode both
```

Record preference answers received in chat:

```bash
python <SKILL_DIR>/scripts/manage_run_state.py set-preferences \
  --state <run_dir>/workflow_state.json \
  --audience general-technical \
  --focus "method and strongest experiments" \
  --coverage "standard full-paper walkthrough"
```

After creating the local voice page, set the intentional pause:

```bash
python <SKILL_DIR>/scripts/manage_run_state.py wait-for-voice \
  --state <run_dir>/workflow_state.json \
  --menu <run_dir>/voice-menu/index.html
```

The user-facing message should be short and explicit:

```text
普通话音色试听页已经准备好。请打开链接，分别试听女声和男声；听完回到这个对话框，直接回复“女声 D，男声 B”（也可写完整音色 ID）。我会从这里继续，自动完成网页、剧本、预览检查、正式视频和最终验收。
```

When the user replies, pass the reply to the state tool rather than asking them to translate it into configuration:

```bash
python <SKILL_DIR>/scripts/manage_run_state.py select-voices \
  --state <run_dir>/workflow_state.json \
  --reply "女声 D，男声 B"
```

The command accepts the A–D labels, full `zf_*` / `zm_*` IDs, or a reply containing “默认”. It writes `voice_casting.json`, changes the state to `running`, and sets the next action to finish all requested deliverables and QA.

After release checks pass, record the delivered files:

```bash
python <SKILL_DIR>/scripts/manage_run_state.py complete \
  --state <run_dir>/workflow_state.json \
  --site <run_dir>/site/index.html \
  --video <run_dir>/final.mp4
```

`workflow_state.json` can contain an absolute local PDF path, so keep it in the private run directory. Never copy it into the Skill repository or a public delivery package.

## Resume behavior

At the start of any continuation turn:

- Find and read the current run's `workflow_state.json`.
- If its status is `awaiting_voice_choice`, interpret the newest user message as a possible voice answer before discussing anything else.
- If the answer is valid, acknowledge the selected pair in one sentence and continue immediately.
- If only one role is identifiable, ask only for the missing role; do not restart the preference checkpoint.
- If the user changes audience, focus, coverage, or language in the same reply, update those fields and honor the change before rendering.
- If the user explicitly changes an already approved voice after full rendering has begun, explain that the audio/video must be rerendered and proceed when this remains within the requested scope.

The state file improves recovery; it does not replace the conversation. Keep all human decisions visible and understandable in chat.

## Legitimate reasons to pause again

Pause after voice selection only when at least one of these is true:

- the source is missing, unreadable, encrypted, or requires access the user has not granted;
- an online provider would introduce a new privacy or paid-service boundary;
- a required credential or system dependency cannot be repaired locally;
- strict evidence, web, audio, or video QA fails in a way that requires a subjective tradeoff;
- the user's latest instruction materially changes the requested output, cost, or publication scope.

Do not pause merely to show a storyboard, ask whether to continue, or request approval of an internal four-turn preview. Those are internal quality gates after the voice choice.
