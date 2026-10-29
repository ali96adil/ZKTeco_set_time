// Host-only regression checks for M2 mobile UI and non-writing firmware.
// Run: node tests/clock_ui.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('src/main.cpp','utf8');
assert(!source.includes('CMD_SET_TIME'), 'M2 must not contain SET_TIME');
assert(!source.includes('/api/set'), 'M2 has no time-write endpoint');
assert(source.includes('CMD_GET_TIME'), 'M2 must support read time');
const match = source.match(/const char PAGE\[\] PROGMEM = R"HTML\(([\s\S]*?)\)HTML";/);
assert(match, 'missing embedded dashboard');
const html = match[1];
assert(html.includes('إدخال يدوي'), 'missing manual preview');
assert(html.includes('مزامنة الهاتف'), 'missing phone preview');
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert(script, 'missing embedded JS');

const elements = new Map();
function element(id) {
 if(!elements.has(id)){
  elements.set(id,{
   textContent:'',className:'',disabled:false,hidden:false,value:'',
   classList:{toggle(){return true;}},
   addEventListener(_name, handler){this.onclick=handler;}
  });
 }
 return elements.get(id);
}
const ctx = vm.createContext({
 document:{getElementById:element},
 Date,Intl,console,
 setInterval(){return 0;},
 fetch(){throw Error('Not expecting an HTTP request')}
});
vm.runInContext(script,ctx,{filename:'embedded-m2-ui.js'});

assert.equal(vm.runInContext("parseBaghdadManual('2024-02-29T12:00:00')",ctx),
 Date.parse('2024-02-29T09:00:00Z'));
assert.throws(()=>vm.runInContext("parseBaghdadManual('2026-02-29T12:00:00')",ctx));
assert.throws(()=>vm.runInContext("parseBaghdadManual('2026-13-01T12:00:00')",ctx));
assert.throws(()=>vm.runInContext("parseBaghdadManual('2026-10-29T25:00:00')",ctx));
assert(vm.runInContext("baghdadParts(Date.parse('2026-10-29T09:00:00Z'))",ctx)
 .includes('12:00:00'), 'must show Baghdad wall clock, not browser zone');

// Inject only time sample for a preview; no network/write calls.
vm.runInContext('measuredOffsetMs=151000; measuredAtMs=Date.now();',ctx);
element('preview').onclick();
assert(!element('previewResult').hidden);
assert(element('shift').textContent.startsWith('−'),'phone sync must permit backward adjustment');
assert(element('warning').textContent.includes('يرجع'),'backward warning required');

element('manualMode').onclick();
element('manual').value='2030-01-01T00:00:00';
element('preview').onclick();
assert(element('shift').textContent.startsWith('+'), 'manual forward adjustment');
assert(element('proposed').textContent.includes('2030-01-01'), 'manual display');

element('manual').value='2026-02-29T00:00:00';
element('preview').onclick();
assert(element('warning').textContent.includes('غير موجود'),'invalid date rejected');

// Stale sample requires a new device read.
vm.runInContext('measuredAtMs=Date.now()-120000;',ctx);
element('preview').onclick();
assert(element('warning').textContent.includes('اقرأ'), 'stale reading must be blocked');

// The page must never have any implementation that writes to terminal.
assert(!/fetch\(\s*['"]\/api\/(sync|set|time\/set)/.test(html));
console.log('M2 UI dry-run tests: PASS');
