/**
 * The cross-table rule for this pack: every dish served must have a retained sample.
 *
 * This is the rule that could not be expressed before. A single-table check can say
 * "this row's weight is under 125 g"; only a join can say "this dish was on the menu
 * and has no sample row at all", which is the failure the regulation is actually
 * about — 对每餐次加工制作的每**种**食品成品进行留样.
 *
 * The reverse direction is reported separately and means something different: a
 * sample for a dish that was never served is a ledger problem, not a kitchen one.
 */

import { joinTables, type JoinResult, type JoinSpec } from './shared/join.ts'
import type { TableInput } from './shared/rows.ts'
import type { Issue, Locator } from './shared/report.ts'

/** The join this pack declares, in one place so the rule and the test agree. */
export const MENU_TO_SAMPLES: JoinSpec = {
  id: 'menu-samples',
  from: { table: 'menu', fields: ['date', 'meal', 'dish'] },
  to: { table: 'samples', fields: ['sampleDate', 'meal', 'dish'] },
  match: { mode: 'loose' },
}

/**
 * Turn a join result into issues.
 *
 * @param result - from {@link joinTables}.
 * @param ruleId - the rule this check answers to.
 * @param basis - the citation line, already rendered.
 * @param labels - human labels for the two tables.
 * @returns issues in the canonical shape.
 */
export function issuesOf(
  result: JoinResult,
  ruleId: string,
  basis: string,
  labels: { from: string; to: string },
): Issue[] {
  const issues: Issue[] = []
  const add = (locator: Locator, found: string, expected: string, fix: string): void => {
    const id = `${ruleId}.${hashOf(locator)}`
    issues.push({
      id,
      ruleId,
      severity: 'error',
      locator,
      found,
      expected,
      basis,
      fix,
    })
  }

  for (const entry of result.missingInTo) {
    add(
      { table: labels.from, row: entry.from.row },
      `${labels.from}有这一行，${labels.to}里没有对应记录（${entry.from.fields['dish'] ?? entry.key}）`,
      `每道供餐菜品都应有留样记录`,
      '补留样或说明未留样原因；本条只核对两份台账能否对上，不判断现场是否确实留过',
    )
  }
  for (const entry of result.missingInFrom) {
    add(
      { table: labels.to, row: entry.to.row },
      `${labels.to}有留样，${labels.from}里找不到这道菜（${entry.to.fields['dish'] ?? entry.key}）`,
      `留样记录应对应实际供餐的菜品`,
      '核对菜单或留样记录，确认哪一侧写错了',
    )
  }
  for (const entry of result.emptyKeys) {
    add(
      { table: entry.side === 'from' ? labels.from : labels.to, row: entry.row.row },
      `${entry.side === 'from' ? labels.from : labels.to}这一行的日期/餐次/菜品不完整，无法与另一份台账对上`,
      '三个键都要有值才能比对',
      '补齐日期、餐次、菜品名称',
    )
  }
  return issues
}

/** A small hash so an issue id is stable without importing the report internals twice. */
function hashOf(locator: Locator): string {
  // The canonical hash lives in report.ts and takes the same shape; importing it here
  // would create a cycle through rows.ts, so the field list is repeated deliberately.
  const keys = ['file', 'page', 'para', 'line', 'row', 'cell', 'column', 'table'] as const
  let hash = 0x811c9dc5
  for (const key of keys) {
    const value = (locator as Record<string, string | number | undefined>)[key]
    if (value === undefined) continue
    const chunk = `${key}=${String(value)};`
    for (let index = 0; index < chunk.length; index++) {
      hash ^= chunk.charCodeAt(index)
      hash = Math.imul(hash, 0x01000193) >>> 0
    }
  }
  return hash.toString(16).padStart(8, '0')
}

/**
 * Run the cross-table check.
 *
 * @param menu - the served-dishes table.
 * @param samples - the retained-samples table.
 * @param ruleId - the rule this answers to.
 * @param basis - the citation line.
 * @param labels - human labels for the two tables.
 * @returns issues, plus the raw join result for the report.
 */
export function checkMenuCoverage(
  menu: TableInput,
  samples: TableInput,
  ruleId: string,
  basis: string,
  labels: { from: string; to: string },
): { issues: Issue[]; join: JoinResult } {
  const join = joinTables(menu, samples, MENU_TO_SAMPLES)
  return { issues: issuesOf(join, ruleId, basis, labels), join }
}
