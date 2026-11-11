# Cortensor Hackathon #5 — what submission actually requires

Source of truth: [Hackathon #5 docs](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5) and the [DoraHacks listing](https://dorahacks.io/hackathon/2418/detail) (id 2418). Dates on the docs page are Pacific Time; DoraHacks shows the live cutoff as **2026-12-19 07:59 UTC = 2026-12-19 13:29 IST**.

Nothing below has been published or submitted. Each step needs an explicit OK.

## Scoring (so we know what to include)

- Working functionality and useful outcome — 25%
- Meaningful OpenMinion SDK usage — 20%
- Reproducibility and demo quality — 20%
- Building-block findings and improvement feedback — 25%
- Relevance to Cortensor builder workflows — 10%

Portal / Gemma4 testing is optional and not required. Bug-report + fix-PR bonus needs a confirmed-in-scope report first.

## Prize notes

Pool is **1,150 USD**, paid in **$COR** (50% liquid up front, 50% in a one-month Cortensor staking lock):

- 1st $500, 2nd $300, 3rd $200, 4th $100, 5th $50

A winning team names one payout recipient. Cortensor may ask for identity / eligibility checks. OpenMinion itself has no token.

## Exact materials the PR must contain

From the official Submission Checklist:

1. A **public source repository** and a README with setup and run instructions.
2. A short explanation of the **OpenMinion SDK workflow** (this is in the README).
3. **One working example** and a **1–5 minute demo video** showing the agent running and its result (`demo/rulesminion-demo.mp4`).
4. A **Building Blocks Tested** note: what we used, what worked, what did not.
5. A **What We Learned** note with actionable product feedback.

Those last two live together in `SDK_FEEDBACK.md`.

Keep secrets out of the public repo (`.env` is gitignored; do not commit `.openminion/` runtime state).

## Steps that need Sahil's OK

Do these in order. Do not create a GitHub repo, push, open a PR, post a BUIDL, or share a wallet until each item is approved.

1. **Create a public GitHub repo under Predestinator** named `rulesminion` (or similar) and push this local git history. Do not use Mayaverse-dev.
2. **Star / follow** [OpenMinion/openminion](https://github.com/OpenMinion/openminion) and Cortensor on GitHub, plus OpenMinion and Cortensor on X — the official "How to Participate" list asks for this.
3. **Open a pull request to the dedicated Hackathon #5 repository**, linking the public project, the README, `SDK_FEEDBACK.md`, the working example, and the demo video. As of 11 Nov 2026 the official docs still say *"The repository URL will be added before kickoff."* Recheck [the rules page](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5) and the DoraHacks announcements / Discord before opening anything. If the repo is still unpublished, wait — do not invent a destination.
4. **Submit a BUIDL on DoraHacks** for hackathon 2418 (`https://dorahacks.io/hackathon/2418/detail` → Submit Build). The embedded record marks `mandatoryGitRepoLink` and `mandatoryVideoLink` as true, so expect to paste the public repo URL and the demo video URL. Account login is an identity step.
5. **Host or link the demo video** somewhere the judges can play it (GitHub `demo/` is enough if the repo is public; YouTube / Drive only if asked).
6. **Provide a $COR-capable wallet** if we place, for the 50/50 liquid + one-month stake split. Do not generate or publish a wallet until payout instructions are out and Sahil asks for one.
7. Optional later: file the OpenMinion task-context reproduction as a GitHub issue (and only then a fix PR) if we want the bug-report bonus.

## What is already done locally (no OK needed)

- Working agent, CLI, web UI
- Offline tests and live page fetches
- Honest SDK feedback
- Local git repo (no remote)
- Demo recording under `demo/`

## What this project does *not* do

- It does not call Cortensor Portal or Gemma4 (no access).
- It does not submit itself.
- It does not create or push any GitHub repository.
