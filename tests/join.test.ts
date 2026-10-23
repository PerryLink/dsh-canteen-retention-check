/**
 * Cross-table join: does every served dish have a retained sample?
 *
 * The join is the only thing in this family that looks at two files at once, so the
 * tests here are about the matching itself: what counts as the same key, and what
 * happens when a key is missing rather than merely different.
 */

import { describe, expect, it } from 'vitest'
import { checkMenuCoverage, MENU_TO_SAMPLES } from '../src/cross.ts'
import { joinTables, keyOf, normaliseKey } from '../src/shared/join.ts'
import type { TableInput } from '../src/shared/rows.ts'

/** Build a table from rows of canonical field maps. */
function table(target: string, rows: Record<string, string>[]): TableInput {
  return { target, header: {}, rows: rows.map((fields, index) => ({ row: index + 1, fields })), columns: [], warnings: [] }
}

const menu = table('菜单', [
  { date: '2026-03-04', meal: '午餐', dish: '红烧肉' },
  { date: '2026-03-04', meal: '午餐', dish: '清炒时蔬' },
  { date: '2026-03-04', meal: '午餐', dish: '番茄蛋汤' },
])

const samples = table('留样台账', [
  { sampleDate: '2026-03-04', meal: '午餐', dish: '红烧肉' },
  { sampleDate: '2026-03-04', meal: '午餐', dish: '清炒时蔬' },
])

describe('key normalisation', () => {
  it('folds width and case so the same value matches', () => {
    expect(normaliseKey('ＮＯ．１２')).toBe(normaliseKey('no.12'))
  })

  it('drops inner spaces in loose mode', () => {
    expect(normaliseKey('红 烧 肉', { mode: 'loose' })).toBe('红烧肉')
  })

  it('keeps separators out in digits mode', () => {
    expect(normaliseKey('京A-0120', { mode: 'digits' })).toBe('京a0120')
  })

  it('treats a blank component as no key at all', () => {
    // Half a key would join unrelated rows; an empty one must match nothing.
    expect(keyOf(['date', 'meal', 'dish'], { date: '2026-03-04', meal: '', dish: '红烧肉' })).toBe('')
  })
})

describe('join', () => {
  const result = joinTables(menu, samples, MENU_TO_SAMPLES)

  it('reports the dish that was served but never sampled', () => {
    expect(result.missingInTo).toHaveLength(1)
    expect(result.missingInTo[0]?.from.fields['dish']).toBe('番茄蛋汤')
  })

  it('does not report the dishes that were sampled', () => {
    expect(result.matched).toHaveLength(2)
  })

  it('has nothing on the sample side that is missing from the menu', () => {
    expect(result.missingInFrom).toHaveLength(0)
  })

  it('keeps the two directions apart', () => {
    // A dish without a sample is a kitchen finding; a sample without a dish is a
    // ledger finding. Collapsing them into one "unmatched" bucket loses which.
    const reversed = joinTables(samples, menu, {
      ...MENU_TO_SAMPLES,
      from: { table: 'samples', fields: ['sampleDate', 'meal', 'dish'] },
      to: { table: 'menu', fields: ['date', 'meal', 'dish'] },
    })
    expect(reversed.missingInTo).toHaveLength(0)
    expect(reversed.missingInFrom).toHaveLength(1)
  })
})

describe('issues', () => {
  const { issues, join } = checkMenuCoverage(menu, samples, 'CF-010', '《X》第四十条：应当留样。', {
    from: '菜单',
    to: '留样台账',
  })

  it('emits one issue per unmatched dish, with both table and row located', () => {
    expect(join.missingInTo).toHaveLength(1)
    expect(issues).toHaveLength(1)
    expect(issues[0]?.locator.table).toBe('菜单')
    expect(issues[0]?.locator.row).toBe(3)
  })

  it('says the check compares two ledgers, not the kitchen', () => {
    expect(issues[0]?.fix).toContain('不判断现场是否确实留过')
  })

  it('gives the issue a stable id across runs', () => {
    const again = checkMenuCoverage(menu, samples, 'CF-010', '《X》第四十条：应当留样。', {
      from: '菜单',
      to: '留样台账',
    })
    expect(again.issues[0]?.id).toBe(issues[0]?.id)
  })
})
