/**
 * dsh-canteen-retention-check — table shape and material contract.
 *
 * The plugin is data-only: this file declares which columns the ledger may use and
 * how they map onto canonical names; the shared kit supplies the reader and the
 * check engine, and the rule pack declares every check.
 *
 * The ledger is a single table — one row per retained sample. It is deliberately
 * not joined against a menu: a missing menu row means "we cannot prove which
 * dishes were served", which is a different finding from "this row is wrong", and
 * conflating them would report a shortage the kitchen cannot act on.
 */

import { canonicaliseRow, parseTable, type TableSpec } from './shared/table.ts'
import { runTableCheck, type TableCheckOptions, type TableInput } from './shared/rows.ts'
import type { Ruleset } from './shared/rules.ts'

/** Tool id exposed to the model, and the row id in `cordis.patch.yml`. */
export const TOOL_NAME = 'canteen_retention_check'

/** The ledger's column aliases, declared once so both the spec and the guard see them. */
const COLUMNS = {
  meal: ['餐次', '餐別', '早餐', 'meals', 'meal'],
  foodName: ['留样食品名称', '食品名称', '留样品名', '名称', 'foodName'],
  sampleWeight: ['留样量', '留样重量', '留样数量', 'sampleWeight'],
  unit: ['单位', '计量单位', 'unit'],
  sampledAt: ['留样时间', '留样日期时间', '留样datetime', 'sampledAt'],
  removedAt: ['出柜时间', '销毁时间', '留样结束时间', 'removedAt'],
  keeper: ['留样人员', '留样人', '记录人', 'keeper'],
  storage: ['存放条件', '保存条件', '冷藏', 'storage'],
  remark: ['备注', '说明', 'remark'],
} as const

/** How the material declares its table. */
export const SPEC: TableSpec = {
  rowKeys: ['rows', 'items', 'samples', '留样', '留样记录'],
  columns: COLUMNS,
  header: {
    canteen: ['canteen', '食堂名称', '单位名称'],
    period: ['period', '期间', '月份'],
    checkedAt: ['checkedAt', '核对日期', '检查日期'],
    basis: ['basis', '依据'],
  },
}

/** Fields the material must carry somewhere for the reader to accept it. */
export const REQUIRE_ANY_OF = ['留样食品名称', 'foodName', '留样量', 'sampleWeight', '留样时间', 'sampledAt']

/**
 * Parse the material and attach its canonical field names.
 *
 * @param source - JSON or YAML text.
 * @param target - description of where the material came from.
 * @returns the normalised table, with each row's aliases resolved to field names.
 */
export function parseMaterial(source: string, target: string): TableInput {
  const table = parseTable(source, target, { ...SPEC, requireAnyOf: REQUIRE_ANY_OF })
  for (const row of table.rows) canonicaliseRow(row, SPEC)
  return table
}

/**
 * Run the rule pack against the material.
 *
 * @param input - normalised table.
 * @param ruleset - validated rule pack.
 * @param options - plugin identity, clock value, rule selection and overrides.
 * @returns the report.
 */
export function runCheck(input: TableInput, ruleset: Ruleset, options: TableCheckOptions) {
  return runTableCheck(input, ruleset, options)
}

export type { TableCheckOptions, TableInput }
