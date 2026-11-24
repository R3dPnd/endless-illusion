// Run with `node --require <shim> bind_shim_probe.js`: prints the address each listen() form bound.
const net = require('net')
const forms = [
  (s, cb) => s.listen(0, cb),
  (s, cb) => s.listen(0, '0.0.0.0', cb),
  (s, cb) => s.listen(0, '::', cb),
  (s, cb) => s.listen({ port: 0, host: '::' }, cb),
  (s, cb) => s.listen({ port: 0 }, cb),
]
const out = []
let i = 0
const next = () => {
  if (i === forms.length) { console.log(JSON.stringify(out)); return }
  const s = net.createServer()
  forms[i++](s, () => { out.push(s.address().address); s.close(next) })
}
next()
