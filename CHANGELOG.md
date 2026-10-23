# Changelog

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
