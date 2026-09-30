---
kind: decision
title: A Claude pass classifies every unknown token as name / transparent / artifact / vocab before i+1; only vocab stays unknown
covers: autoanki/vocab_judge.py
---

## What was chosen

After the noise filter, `cli.py` collects every token that
`morph.unknown_morphs` flags across the episode (231 for Meet Yourself
EP1), with one example sentence each, and `vocab_judge.judge` sends them
to Claude in batches of 120 with a fixed rubric:

- `name`: people, places, brands, nicknames, surname + title (刘先生, 燕郊)
- `transparent`: known words whose meaning is just their sum (生日快乐, 两万多, 喝点)
- `artifact`: segmenter cut in the wrong place (人讨 in 讨不讨厌, 有妈)
- `vocab`: real words or fixed expressions to learn (警觉, 燕窝, 逢年过节)

Each line carries a hint computed in code: the token's shortest split into
known words, if one exists. Everything except `vocab` is added to the known
set, which then drives the i+1 filter and the highlight. This runs before
i+1, because a line with a name plus one real word has two raw unknowns and
would otherwise be dropped.

Verdicts are cached in `$AUTOANKI_CACHE/vocab_judgments.json`, keyed by
token, and discarded when the profile's `updated_at` changes, since
"transparent" depends on what the learner knows. Re-running an episode is
deterministic and later episodes reuse shared tokens. `--no-vocab-judge`
skips the pass.

On EP1, the first 136-card deck highlighted a name or a split-into-known
compound on 112 cards (生日快乐, 丽萨, 人讨). The pass classified the 231
tokens as 15 name, 95 transparent, 38 artifact, and 83 vocab. The rebuilt
deck has 59 cards, and every highlight is a real word (警觉, 胃镜, 燕窝, 迷茫,
胰腺癌, 逢年过节, 硬指标); none is a name or a split-into-known compound.

## What was rejected, and why

- **Dictionary lookup (CC-CEDICT) as the test.** 生日快乐 and 过生日 are
  dictionary entries but teach nothing to someone who knows 生日 and 快乐.
  Whether a compound is lexicalized is a judgment, which CLAUDE.md §3 routes
  to an agent with a rubric.
- **"Splits into known words" = known.** It would discard 餐券-type
  borderline words and 逢年过节-type idioms whose parts are all known. The
  split is passed as evidence, not used as the rule.
- **jieba POS tags for names.** They tagged 谢谢, 祝您 and 小姨 as `nr`
  (person name) and 丽萨 as `ns` (place).
- **Judging only the highlighted token on already-kept cards.** Misses lines
  whose second unknown is a name, which should become valid i+1 cards.

## Known misjudgment

柯基 (corgi) was labelled `name`. The rubric's tie-break ("when unsure,
vocab") covers transparent-vs-vocab only.
