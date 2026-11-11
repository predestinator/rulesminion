# How to submit RulesMinion

Nothing below has been published. Each step needs an explicit OK.

Official rules: [Hackathon #5 docs](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5) and the [DoraHacks listing](https://dorahacks.io/hackathon/2418/detail). Deadline on DoraHacks: 19 December 2026, 07:59 UTC, which is **19 December 2026, 1:29 PM IST**. Docs also mention 18 December 2026 Pacific Time; trust the DoraHacks cutoff.

Prize pool: $1,150 USD paid in $COR. 1st $500, 2nd $300, 3rd $200, 4th $100, 5th $50. For each award, 50% is liquid $COR and 50% sits in a one-month Cortensor staking lock. A winning team names one payout address.

## What the judges asked for

A submission needs:

1. A **public source repository** and a README with setup and run instructions.
2. A short explanation of the OpenMinion SDK workflow (this repo: README + `SDK_FEEDBACK.md`).
3. One working example and a **1–5 minute demo video**.
4. A **Building Blocks Tested** note: what was used, what worked, what did not.
5. A **What We Learned** note with actionable product feedback.
6. A functioning, reproducible agent that uses the OpenMinion 0.1 Python SDK as a meaningful part of its runtime.

Scoring: working functionality 25%, meaningful SDK usage 20%, reproducibility and demo quality 20%, building-block findings 25%, relevance to Cortensor builder workflows 10%. Portal/Gemma4 testing is bonus only; we do not have Portal access.

## Steps that need Sahil's OK

1. **Create a public GitHub repo under Predestinator** named `rulesminion` (or similar) and push this local git history. Do not use Mayaverse-dev. Ask before making the repo public.
2. **Star / follow** [OpenMinion](https://github.com/OpenMinion/openminion) and Cortensor on GitHub and X, as the participate checklist asks. Optional but listed in the official how-to.
3. **Upload or link the demo video** (`demo/rulesminion-demo.mp4`, about 80 seconds) so the public README can point at it (GitHub file, or YouTube if you prefer).
4. **Open a pull request** to the dedicated Hackathon #5 submission repository, linking the public repo, the demo, `SDK_FEEDBACK.md`, and this file. As of 11 November 2026 the official docs still say “the repository URL will be added before kickoff.” Recheck the docs and Discord before filing the PR.
5. **Create a DoraHacks BUIDL** on [hackathon 2418](https://dorahacks.io/hackathon/2418/detail) (“Submit Build”), pointing at the same public repo and demo.
6. **Provide a $COR-capable wallet** if the project places. Cortensor pays in $COR, half liquid and half staked for one month. Do not put a wallet address in the public repo until you choose one.

Identity, KYC, or eligibility checks may be required before payout.

## What is already done locally

- Working CLI and web UI
- Real extracts against the DoraHacks page, the official docs page, and Learn AR with SPECS on Devpost
- Offline tests and an honest SDK feedback write-up
- Demo mp4/gif and sample JSON
- Local git commit only: no GitHub repo, no push, no PR, no DoraHacks entry
