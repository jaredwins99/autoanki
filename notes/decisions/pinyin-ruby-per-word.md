---
kind: decision
title: Tone-marked pinyin per jieba word as ruby on the card back, never on the Reading front
covers: autoanki/pinyin.py
---

## What was chosen

`pinyin_ruby(text)` segments with jieba and renders each word as
`<ruby>行李牌<rt>xínglǐpái</rt></ruby>` using pypinyin `Style.TONE`. It fills
a `Pinyin` note field. Both card backs show it in place of the plain
`SegmentedChinese` line, falling back to that line for older notes without
`Pinyin` (`{{#Pinyin}}…{{^Pinyin}}…`). The Reading card's front stays
characters-only.

Requested so the learner can read the secondary words on a card, not just
the highlighted new one.

## What was rejected, and why

- **Pinyin per character.** pypinyin resolves characters with several
  readings (行 in 行李 vs 银行, 了, 得) from its phrase dictionary, which
  needs the word, not the lone character.
- **Pinyin on the Reading front.** It gives away the reading the card is
  testing.
- **Keep the separate "退房 / 吗" segmented line as well.** The ruby line
  already shows word boundaries; two lines of the same segmentation is
  clutter.
- **Tone numbers (tui4fang2).** Marks are what learners read in
  dictionaries and textbooks.
