import { describeTablePlugin } from './table-plugin-suite.ts'
import { Config } from '../src/config.ts'
import { parseMaterial, runCheck, SPEC } from '../src/model.ts'
import { buildView } from '../src/view.ts'
import { inject, name, resolvePackageFile, TOOL_NAME } from '../src/index.ts'

/** A minimal well-formed ledger: one row carrying all four record elements. */
const good = {
  target: '2026 年 3 月 4 日食堂留样台账',
  rows: [
    {
      餐次: '午餐',
      留样食品名称: '红烧肉',
      留样量: '125',
      留样时间: '2026-03-04 11:40',
      出柜时间: '2026-03-06 11:40',
      留样人员: '张三',
    },
  ],
}

/**
 * A ledger carrying none of the columns the spec knows.
 *
 * This is the reader's boundary: a worksheet with the wrong headers must be
 * refused, not silently checked against zero rows and reported as clean.
 */
const unknownColumn = {
  target: '2026 年 3 月 4 日食堂留样台账',
  rows: [{ 不存在的列: 'x', 另一个不存在的列: 'y' }],
}

describeTablePlugin({
  name,
  inject,
  TOOL_NAME,
  resolvePackageFile,
  Config,
  rulesFile: 'rules/canteen-retention.yaml',
  parseMaterial,
  runCheck,
  buildView,
  columnNames: SPEC.columns,
  samples: { good, unknownColumn },
})
