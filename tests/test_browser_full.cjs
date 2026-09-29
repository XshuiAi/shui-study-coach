// Full user-flow regression. Fixed fixtures only; no output paths or file writes.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const q=JSON.parse(fs.readFileSync(path.join(root,'examples/cet6-careful-reading.json'),'utf8'));
const generic=JSON.parse(fs.readFileSync(path.join(root,'examples/english-reading.json'),'utf8'));
const render=quiz=>execFileSync('python3',[path.join(root,'scripts/render_quiz.py')],{input:JSON.stringify(quiz),encoding:'utf8'});
const pages={'/quiz':render(q),'/generic':render(generic)};
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.statusCode=pages[req.url]?200:404;res.end(pages[req.url]||'Not found');});
const click=(p,id)=>p.locator('#'+id).click();
const visible=(p,id)=>p.locator('#'+id).waitFor({state:'visible'});
const nav=(p,id)=>p.locator('[data-page="'+id+'"]').click();
const importData=(p,data)=>p.locator('#import-file').setInputFiles({name:'record.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
async function readDownload(p,id){const pending=p.waitForEvent('download');await click(p,id);const download=await pending;const stream=await download.createReadStream();const parts=[];for await(const chunk of stream)parts.push(chunk);return JSON.parse(Buffer.concat(parts).toString());}
async function noOverflow(p){assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page overflows viewport');}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,...(process.env.STUDY_TEST_CHROME==='1'?{channel:'chrome'}:{})});
 try{
  const errors=[];
  const fresh=async(width=1280)=>{const p=await browser.newPage({viewport:{width,height:900}});p.setDefaultTimeout(12000);p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>{errors.push('unexpected native modal');d.dismiss();});return p;};
  const p=await fresh();await p.goto(base+'/quiz');
  await nav(p,'records');assert(await p.locator('#resume-record').isDisabled());assert(await p.locator('#export-current').isDisabled());
  await nav(p,'welcome');await p.locator('[name="mode"][value="exam"]').check();await click(p,'start');assert(!(await p.locator('#hint').isVisible()));assert(await p.locator('#prev').isDisabled());
  await click(p,'flag');assert.equal(await p.locator('#flag').getAttribute('aria-pressed'),'true');await click(p,'flag');
  await p.locator('#options input').nth(q.questions[0].answer[0]).check();
  const draft=await readDownload(p,'save');assert.equal(draft.submitted,false);
  await click(p,'submit');await p.keyboard.press('Escape');assert(!(await p.locator('#confirm-panel').isVisible()));await visible(p,'work');
  await nav(p,'welcome');await importData(p,{...draft,fingerprint:'wrong'});assert.match(await p.locator('#message').textContent(),/无法导入/);await click(p,'start');assert.match(await p.locator('#counts').textContent(),/已答 1/);
  for(let i=0;i<q.questions.length;i++){await p.locator('#nav button').nth(i).click();await p.locator('#options input').nth(q.questions[i].answer[0]).check();}assert(await p.locator('#next').isDisabled());
  await click(p,'submit');await p.keyboard.press('Tab');assert.equal(await p.evaluate(()=>document.activeElement.id),'confirm-yes');await p.keyboard.press('Enter');await visible(p,'report');assert.match(await p.locator('#score').textContent(),/5.*5/);assert(!(await p.locator('#followup-offer').isVisible()));
  await p.locator('#filter').selectOption('review');assert.match(await p.locator('#cards').textContent(),/没有题目/);await p.locator('#filter').selectOption('all');assert.equal(await p.locator('#cards>article').count(),5);
  const completed=await readDownload(p,'export-report');assert(completed.submitted);await click(p,'restart');await click(p,'confirm-yes');await visible(p,'welcome');assert(!(await p.locator('[name="mode"][value="practice"]').isDisabled()));
  await nav(p,'records');assert.match(await p.locator('#records-list').textContent(),/5\/5/);await nav(p,'welcome');await importData(p,completed);await visible(p,'report');
  await nav(p,'records');assert.match(await p.locator('#records-list').textContent(),/5\/5/);
  // Import into a fresh browser must populate history and the next-review plan.
  const restored=await fresh();await restored.goto(base+'/quiz');await importData(restored,completed);await visible(restored,'report');await nav(restored,'records');assert.match(await restored.locator('#records-list').textContent(),/5\/5/);
  await nav(restored,'plan');assert((await restored.locator('#plan-due').inputValue()).length===10);
  await nav(restored,'welcome');await importData(restored,draft);await visible(restored,'confirm-panel');await click(restored,'confirm-no');await click(restored,'start');await visible(restored,'report');
  // Plan persistence, validation, task check-off, and unfinished second round.
  const practice=await fresh();await practice.goto(base+'/quiz');await click(practice,'start');await practice.locator('#options input').nth(q.questions[0].answer[0]).check();await click(practice,'hint');await click(practice,'flag');
  await click(practice,'submit');await click(practice,'confirm-yes');await visible(practice,'report');await practice.locator('#filter').selectOption('flagged');assert.equal(await practice.locator('#cards>article').count(),1);
  await nav(practice,'plan');await practice.locator('#plan-minutes').fill('0');await click(practice,'save-plan');assert.match(await practice.locator('#plan-status').textContent(),/1–240/);
  await practice.locator('#plan-minutes').fill('20');await practice.locator('#plan-goal').fill('六级阶段复习');await practice.locator('#plan-due').fill('2026-10-10');await practice.locator('#plan-exam').fill('2026-12-12');await practice.locator('#plan-tasks input').nth(0).check();await click(practice,'save-plan');
  const plan=await readDownload(practice,'export-plan');assert.equal(plan.goal,'六级阶段复习');assert.equal(plan.minutes,20);assert.equal(plan.tasks[0],true);
  await practice.reload();await nav(practice,'plan');assert.equal(await practice.locator('#plan-due').inputValue(),'2026-10-10');assert(await practice.locator('#plan-tasks input').nth(0).isChecked());
  await nav(practice,'welcome');await click(practice,'start');await click(practice,'begin-followup');assert.equal(await practice.locator('.followup-question').count(),5);await practice.locator('.followup-question').first().locator('input').nth(q.followups[0].answer[0]).check();
  await practice.reload();await visible(practice,'welcome');await click(practice,'start');await visible(practice,'followup-work');assert(await practice.locator('.followup-question').first().locator('input').nth(q.followups[0].answer[0]).isChecked());
  await click(practice,'submit-followup');await click(practice,'confirm-yes');await nav(practice,'plan');assert(await practice.locator('#plan-tasks input').nth(0).isChecked(),'manual check-off must survive followup submission');
  // Single/multiple/truefalse all use the same generated template.
  const g=await fresh();await g.goto(base+'/generic');await click(g,'start');
  for(let i=0;i<generic.questions.length;i++){await g.locator('#nav button').nth(i).click();for(const answer of generic.questions[i].answer)await g.locator('#options input').nth(answer).check();}
  await click(g,'submit');await click(g,'confirm-yes');assert.match(await g.locator('#score').textContent(),/4.*4/);
  // Responsive layout and keyboard-reachable navigation across main screens.
  for(const width of [320,390,768,1440]){const mobile=await fresh(width);await mobile.goto(base+'/quiz');for(const section of ['welcome','materials','plan','records']){await nav(mobile,section);await noOverflow(mobile);}await nav(mobile,'welcome');await click(mobile,'start');await noOverflow(mobile);await click(mobile,'jump-question');const box=await mobile.locator('#prompt').boundingBox(),bar=await mobile.locator('.app-nav').boundingBox();assert(box.y>=bar.y+bar.height-1,'sticky navigation must not cover question heading');await click(mobile,'submit');await noOverflow(mobile);await click(mobile,'confirm-yes');await noOverflow(mobile);await click(mobile,'begin-followup');await noOverflow(mobile);await mobile.close();}
  assert.deepEqual(errors,[]);console.log('PASS: exam, flags, filters, keyboard confirmation, valid/invalid/cancelled imports, restored history/plan, restart, JSON download contents, plan validation/check-offs, second-round refresh, mixed question types, 320/390/768/1440 layouts.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
