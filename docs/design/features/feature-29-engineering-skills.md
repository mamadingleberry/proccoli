# Feature 29: Engineering skills

Plan: [plan/features/feature-29-engineering-skills.md](../../plan/features/feature-29-engineering-skills.md)

*Built.* The generic standards come from the `engineering-skills` plugin; ours add the rest and win where they differ ([the plan](../../plan/features/feature-29-engineering-skills.md) lists the four differences).

```mermaid
flowchart TB
    PE["proccoli-engineer<br/>(SysRoot, System, build_context, make ui-test)"]
    SP["software-project"]
    SD["software-design"]
    ST["software-testing"]
    AD["application-design"]
    ES["engineering-skills plugin<br/>senior-architect · tdd-guide · red-green-proof · code-reviewer …"]
    PE --> SP
    SP --> ES
    SP --> SD & ST & AD
    SD & ST & AD -. "add to, win where they differ" .-> ES
```

The general skills say *what* good practice is; `proccoli-engineer` says
*where* that lives in this repo.
