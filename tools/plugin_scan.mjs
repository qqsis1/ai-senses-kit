// 插件装前静态扫描：装之前先看清它要什么。
// 用法: node tools/plugin_scan.mjs <插件目录或包名> [更多...]
// 输出: DSH 版本范围是否匹配、peer 是否被钉死、有没有安装脚本、源码里的网络/子进程/文件/凭据/环境变量痕迹、大文件。
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { join, extname, relative } from 'node:path'
import { execFileSync } from 'node:child_process'
import { homedir } from 'node:os'

const DSH_HOME = process.env.DSH_HOME || join(homedir(), '.dsh')

const DSH_VERSION = (() => {
  try { return execFileSync('cmd.exe', ['/c', 'dsh', '--version'], { encoding: 'utf8', timeout: 20000 }).trim().split(/\s+/)[0] } catch { return 'unknown' }
})()

const ver = (s) => String(s).replace(/^v/, '').split('.').map(x => parseInt(x, 10) || 0)
const cmp = (a, b) => {
  const A = ver(a), B = ver(b)
  for (let i = 0; i < 3; i++) if (A[i] !== B[i]) return A[i] > B[i] ? 1 : -1
  return 0
}
function satisfies(range, v) {
  if (!range || range === '*' || range === 'latest') return true
  const parts = String(range).split(/\s+/).filter(Boolean)
  for (const p of parts) {
    const m = p.match(/^(>=|<=|>|<|\^|~|=)?(.*)$/)
    const op = m[1] || '='
    const target = m[2].trim()
    if (!target) continue
    // 粗略处理：比较前三段数字，预发布标签按数字段比较（够用，不精确）
    const c = cmp(v, target)
    if (op === '>=' && c < 0) return false
    if (op === '>' && c <= 0) return false
    if (op === '<=' && c > 0) return false
    if (op === '<' && c >= 0) return false
    if ((op === '^' || op === '~' || op === '=') && c !== 0) return false
  }
  return true
}

function resolveDir(arg) {
  if (existsSync(arg)) return arg
  const profiles = join(DSH_HOME, 'profiles')
  if (existsSync(profiles)) {
    for (const p of readdirSync(profiles)) {
      const cand = join(profiles, p, 'node_modules', arg)
      if (existsSync(cand)) return cand
    }
  }
  return null
}

function walk(dir, base = dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === '.git') continue
    const p = join(dir, name)
    let st
    try { st = statSync(p) } catch { continue }
    if (st.isDirectory()) walk(p, base, out)
    else out.push({ p, rel: relative(base, p).split('\\').join('/'), size: st.size })
  }
  return out
}

const RISK = [
  ['网络请求', /https?:\/\/(?!localhost|127\.0\.0\.1)|fetch\(/i],
  ['起子进程', /child_process|\bexec\(|\bspawn\(|execSync|spawnSync/],
  ['读写本地文件', /readFileSync|writeFileSync|appendFileSync|mkdirSync|createWriteStream/],
  ['读环境变量', /process\.env/],
  ['动态求值', /\beval\(|new Function\(/],
  ['读凭据', /credentials/],
]
const HOST_ENV = /(DEEPSEEK_API_KEY|DASHSCOPE_API_KEY|GITHUB_TOKEN|ARK_API_KEY|IMAGE_GEN_PROVIDER_API_KEY)/

const dirs = process.argv.slice(2).map(resolveDir)
if (!dirs.length || dirs.some(d => !d)) { console.error('用法: node tools/plugin_scan.mjs <目录或包名>'); process.exit(2) }

for (const dir of dirs) {
  console.log(`\n=== ${dir} ===`)
  let pkg = {}
  try { pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8')) } catch { console.log('没有 package.json'); continue }
  console.log(`名称 ${pkg.name} ${pkg.version || ''}｜类型 ${pkg.type || '?'}`)
  const range = pkg.engines?.dsh
  console.log(`DSH 要求 ${range || '（未声明）'}｜当前 ${DSH_VERSION}｜${range ? (satisfies(range, DSH_VERSION) ? '✅ 在范围内' : '❌ 不在范围') : '⚠️ 未声明'}`)
  const peers = pkg.peerDependencies || {}
  console.log('peer:', Object.keys(peers).length ? Object.entries(peers).map(([k, v]) => `${k.replace('@deepseek-ai/', '')}@${v}`).join(' ; ') : '（无）')
  console.log('deps:', Object.keys(pkg.dependencies || {}).join(', ') || '（无）')
  const scripts = pkg.scripts || {}
  const danger = Object.keys(scripts).filter(k => /install|prepare|postinstall|preinstall|build/.test(k))
  console.log('脚本:', Object.keys(scripts).length ? Object.keys(scripts).join(', ') : '（无）', danger.length ? `⚠️ 含 ${danger.join('/')}（安装时可能执行）` : '')

  const files = walk(dir)
  const totalKB = files.reduce((a, f) => a + f.size, 0) / 1024
  console.log(`文件 ${files.length} 个 / ${totalKB.toFixed(0)} KB`)
  const code = files.filter(f => ['.js', '.mjs', '.cjs', '.ts'].includes(extname(f.p)) && f.size < 2_000_000)
  const hits = new Map(RISK.map(([n]) => [n, 0]))
  const urls = new Set()
  const envs = new Set()
  for (const f of code) {
    let t = ''
    try { t = readFileSync(f.p, 'utf8') } catch { continue }
    for (const [name, re] of RISK) if (re.test(t)) hits.set(name, hits.get(name) + 1)
    for (const m of t.matchAll(/https?:\/\/[^\s'"`)<>]+/g)) {
      const u = m[0]
      if (!/localhost|127\.0\.0\.1|schema|www\.w3\.org|json-schema/.test(u)) urls.add(u.slice(0, 90))
    }
    for (const m of t.matchAll(/process\.env\.([A-Z0-9_]+)/g)) envs.add(m[1])
    if (HOST_ENV.test(t)) hits.set('⚠️ 触及宿主密钥名', (hits.get('⚠️ 触及宿主密钥名') || 0) + 1)
  }
  console.log('代码痕迹:', [...hits.entries()].filter(([, n]) => n).map(([k, n]) => `${k}×${n}`).join(' · ') || '（无）')
  console.log('外联地址:', [...urls].slice(0, 6).join(' | ') || '（无）')
  console.log('环境变量:', [...envs].slice(0, 8).join(', ') || '（无）')
  const big = files.filter(f => f.size > 1_000_000).map(f => `${f.rel} ${(f.size / 1048576).toFixed(1)}MB`)
  if (big.length) console.log('大文件:', big.slice(0, 5).join(' | '))
}
