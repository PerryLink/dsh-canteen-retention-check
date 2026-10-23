/**
 * Cross-table checks: does every row on one side have a counterpart on the other?
 *
 * Kept separate from `runTableCheck` on purpose. That function's contract is "one
 * table, one row, one verdict", and every one of the family's 37 check kinds is built
 * on it. Adding a second table to that contract would mean every kind has to ask
 * whether the row it is looking at came from a join — a change with no benefit to the
 * fifty-odd packs that only ever see one table.
 *
 * So this is a second entry point. A pack that declares `sources` and `joins` calls
 * it in addition; a pack that does not is unaffected.
 *
 * The one thing this cannot do is decide which side is wrong. A dish with no retained
 * sample is a finding against the kitchen; a sample with no dish is a finding against
 * the ledger. Both are "unmatched", and the rule that declares the join says which
 * direction it cares about.
 */

import type { Row, TableInput } from './rows.ts'

/** How a key cell is normalised before matching. */
export interface MatchOptions {
  /** `exact` trims only; `loose` also folds width and case and drops inner spaces; `digits` keeps alphanumerics and CJK. */
  mode?: 'exact' | 'loose' | 'digits'
  /** Prefixes stripped before matching, in order. */
  strip?: readonly string[]
  caseInsensitive?: boolean
  fullWidth?: boolean
}

/** One side of a join. */
export interface JoinEnd {
  table: string
  fields: readonly string[]
}

/** One declared edge. */
export interface JoinSpec {
  id: string
  from: JoinEnd
  to: JoinEnd
  match?: MatchOptions
  /** Refuse the check when one key maps to more than this many rows. Default 2000. */
  maxFanout?: number
}

/** A declared table. */
export interface SourceSpec {
  id: string
  label: string
  spec: string
  primary?: boolean
}

/** One row of the joined side. */
export interface SideRow {
  table: string
  label: string
  row: number
  fields: Record<string, string>
}

/** The result of joining two sides. */
export interface JoinResult {
  /** Keys present on the from side with no counterpart. */
  missingInTo: { key: string; from: SideRow }[]
  /** Keys present on the to side with no counterpart. */
  missingInFrom: { key: string; to: SideRow }[]
  /** Keys that matched, with counts. */
  matched: { key: string; from: SideRow; to: SideRow[] }[]
  /** Keys whose counterpart list exceeded `maxFanout` and were therefore not compared. */
  fanoutSkipped: string[]
  /** Rows that had an empty key on either side. */
  emptyKeys: { side: 'from' | 'to'; row: SideRow }[]
}

/**
 * Normalise a key cell so two spellings of the same value match.
 *
 * The default is `loose`: a menu writes 「红烧肉」 and a ledger writes 「红烧肉 」 or
 * 「红烧肉(大)」… the last one is not a match, and no normalisation will make it one.
 * What this can fix is width, case and stray spaces, which are transcription noise
 * rather than different values.
 *
 * @param raw - the cell's text.
 * @param options - the rule's matching options.
 * @returns the normalised key.
 */
export function normaliseKey(raw: string | undefined, options: MatchOptions = {}): string {
  if (raw === undefined) return ''
  let text = raw.trim()
  for (const prefix of options.strip ?? []) {
    if (text.startsWith(prefix)) text = text.slice(prefix.length).trim()
  }
  if (options.fullWidth !== false) {
    // NFKC folds full-width digits, letters and punctuation onto their ASCII forms,
    // which is the most common way the same value gets written two ways in a ledger.
    text = text.normalize('NFKC')
  }
  if (options.mode === 'digits') {
    // Keep letters, digits and Han characters only; this drops separators such as
    // the hyphen in a certificate number.
    text = text.replace(/[^\p{L}\p{N}]/gu, '')
  }
  if (options.mode === 'loose') {
    text = text.replace(/\s+/gu, '')
  }
  if (options.caseInsensitive !== false) text = text.toLowerCase()
  return text
}

/**
 * Build a composite key from one row.
 *
 * @param fields - the key columns, in the rule's declared order.
 * @param values - the row's canonical fields.
 * @param options - matching options.
 * @returns the joined key, or empty when any component is blank.
 */
export function keyOf(fields: readonly string[], values: Record<string, string>, options: MatchOptions = {}): string {
  const parts: string[] = []
  for (const field of fields) {
    const part = normaliseKey(values[field], options)
    // An incomplete key must not match: half a key would join unrelated rows.
    if (part === '') return ''
    parts.push(part)
  }
  return parts.join('\u0001')
}

/**
 * Join two tables.
 *
 * @param fromTable - the subject side.
 * @param toTable - the counterpart side.
 * @param join - the edge declaration.
 * @returns the join result.
 */
export function joinTables(fromTable: TableInput, toTable: TableInput, join: JoinSpec): JoinResult {
  const options = join.match ?? {}
  const maxFanout = join.maxFanout ?? 2000
  const fromLabel = fromTable.target
  const toLabel = toTable.target

  const toIndex = new Map<string, SideRow[]>()
  const emptyKeys: JoinResult['emptyKeys'] = []
  toTable.rows.forEach((row: Row, index: number) => {
    const key = keyOf(join.to.fields, row.fields, options)
    const side: SideRow = { table: join.to.table, label: toLabel, row: index + 1, fields: row.fields }
    if (key === '') {
      emptyKeys.push({ side: 'to', row: side })
      return
    }
    const bucket = toIndex.get(key)
    if (bucket === undefined) toIndex.set(key, [side])
    else bucket.push(side)
  })

  const result: JoinResult = { missingInTo: [], missingInFrom: [], matched: [], fanoutSkipped: [], emptyKeys }
  const seenTo = new Set<string>()

  fromTable.rows.forEach((row: Row, index: number) => {
    const key = keyOf(join.from.fields, row.fields, options)
    const side: SideRow = { table: join.from.table, label: fromLabel, row: index + 1, fields: row.fields }
    if (key === '') {
      emptyKeys.push({ side: 'from', row: side })
      return
    }
    const counterparts = toIndex.get(key)
    if (counterparts === undefined) {
      result.missingInTo.push({ key, from: side })
      return
    }
    seenTo.add(key)
    if (counterparts.length > maxFanout) {
      result.fanoutSkipped.push(key)
      return
    }
    result.matched.push({ key, from: side, to: counterparts })
  })

  for (const [key, bucket] of toIndex) {
    if (seenTo.has(key)) continue
    for (const side of bucket) result.missingInFrom.push({ key, to: side })
  }

  return result
}
