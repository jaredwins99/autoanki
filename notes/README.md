# Notes

A note earns its place only if a future reader would otherwise re-derive it or
contradict it. Progress logs are not notes.

    notes/decisions/   what was chosen, and what was rejected, with the reason
    notes/findings/    a fact about the data, with the command that shows it
    notes/open/        a question that is still open, and what it blocks
    notes/reference/   a pointer to something outside the repository

Every note declares the files it covers. `notes/INDEX.md` is generated from
those declarations, so it cannot drift; do not edit it.

    ---
    kind: decision
    title: One sentence a reader can act on
    covers: src/thing.py, scripts/run_thing.py
    ---

A finding adds the claim and the command that establishes it, and the check
re-runs that command:

    ---
    kind: finding
    title: Half the orders have no customer
    covers: src/orders.py
    claim: 49.8% of orders have no customer id
    evidence: python -m scripts.count_customers --summary
    ---

What must be covered is declared in `notes/coverage.ini`, not in the checker:
the directories, the file kinds, what is excluded, and any registry that
already documents a module. Widen it when the project grows a directory or a
language, since code outside the scope is code the check cannot see.

    python correctness/checks/check_notes.py             # structure and coverage
    python correctness/checks/check_notes.py --evidence  # also re-run findings
