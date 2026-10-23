# Changelog

## 0.2.0

Adds the first cross-table rule in the family: every dish on the menu must have a
retained sample.

- **A single table cannot express this.** It can say "this row's weight is under
  125 g"; only a join can say "this dish was served and has no sample row at all" —
  which is what 第四十条 actually requires (「每餐次加工制作的每**种**食品成品」).
- **The two directions are kept apart.** A dish without a sample is a kitchen
  finding; a sample without a dish is a ledger finding. One "unmatched" bucket would
  lose which.
- `Locator.table` is new, so row 3 of the menu and row 3 of the ledger no longer
  render the same, and it participates in the issue id hash.
- **CF-010 lives in `crossRules:`, not `rules:`.** Single-table runs cannot execute
  it, so they list it under 未执行 with the reason — silently omitting it would read
  as "everything ran". No fixture pair is claimed for it, because a fixture cannot
  make a two-file rule run on one file.
- `sync-shared.mjs` now ships `join.ts` and the xlsx writer only to packs that
  import them: an ordinary pack still carries 14 shared modules, this one 15, and
  site-log 16.
- 44 tests.


## 0.1.0

First release. Nine single-table rules over a canteen retention ledger.

- The four record elements and the 125-gram floor come from one quoted clause
  (《学校食品安全与营养健康管理规定》第四十条), so those checks are `direct` and
  may reach `error`.
- The 48-hour window is checked as a whole-day gap and labelled as such, not as a
  quotation of a clause it does not appear in.
- A column absent from the ledger is reported as "not applicable", not as a
  violation on every row: a sheet with the wrong headers is a shape problem, and
  "every row is wrong" would bury it.
- Nine fixture pairs, each violating exactly the rule under test so a failure
  names the cause.
- The pack's field references were rewritten from Chinese labels to the family's
  canonical names (`foodName`, `sampleWeight`, `sampledAt`, `keeper`, `removedAt`,
  `meal`), matching how every other pack in this family addresses columns.
