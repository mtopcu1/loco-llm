#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { fileURLToPath } from 'node:url'

const BUDGET = 1_500_000

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist/assets')
if (!fs.existsSync(dist)) {
  console.error('dashboard/dist/assets not found — run `npm run build` first.')
  process.exit(2)
}

let total = 0
for (const name of fs.readdirSync(dist)) {
  const p = path.join(dist, name)
  const stat = fs.statSync(p)
  if (!stat.isFile()) continue
  const raw = fs.readFileSync(p)
  const gz = zlib.gzipSync(raw, { level: 9 })
  total += gz.length
  console.log(`${name}: ${stat.size} bytes raw, ${gz.length} bytes gzip`)
}

console.log(`---\nTotal gzipped: ${total} bytes (budget ${BUDGET})`)
if (total > BUDGET) {
  console.error(`BUDGET EXCEEDED by ${total - BUDGET} bytes`)
  process.exit(1)
}
