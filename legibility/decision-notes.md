# Decision notes

A repository records what it is; it does not record why it is that way. The
reason a column is dropped, the reason a threshold is 15 and not 10, the fact
that half the orders have no customer — these live in a head, a chat log or a
commit message nobody will find, and the next person re-derives them or
quietly contradicts them.

Notes hold that reasoning, and a check keeps them honest.

## The four failures

A note is worth keeping only while it is true. Four things make it untrue, and
each fails the check rather than waiting to mislead someone:

1. **A note covers a file that no longer exists.** The code moved or went; the
   note now describes nothing.
2. **A source file no note and no registry covers.** Code arrived without a
   reason, which is how a repository fills with decisions nobody can explain.
3. **Two decisions claim the same file.** Two answers to one question; a
   reader cannot tell which holds.
4. **A finding's evidence no longer shows its claim.** The data moved under
   the note. This is the one that matters most: a stale number in a document
   is worse than no number, because it is quoted.

## What is a note, and what is not

A note earns its place only if a future reader would otherwise re-derive it or
contradict it. "Chose Parquet over CSV because the labels are categorical and
CSV lost the dtype" is a note. "Refactored the loader" is not: the diff says
that. Progress logs are not notes.

Four kinds: a **decision** (chosen and rejected, with the reason), a
**finding** (a fact about the data, with the command that shows it), an
**open** question (what it blocks, and what would settle it), and a
**reference** (a pointer outside the repository).

## The scope is declared

`notes/coverage.ini` says which directories and file kinds need covering, what
is excluded, and which registries already document a module. It is declared
rather than written into the checker because a scope hardcoded to one language
and two directories is exactly how code slips outside the check: everything
inside it stays honest, and whatever was left out drifts silently until
somebody audits by hand.

Tests are excluded: a test is read beside the code it tests.

## The index is generated

`notes/INDEX.md` is built from what the notes declare. A hand-kept index
drifts, which is the failure being designed against.
