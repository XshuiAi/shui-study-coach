// Run: node tests/test_browser.cjs (Playwright + Chromium required).
// Serves only the fixed fixture on loopback; does not accept paths or write files.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'examples/cet6-careful-reading.html'),'utf8');
const quiz=JSON.parse(fs.readFileSync(path.join(root,'examples/cet6-careful-reading.json'),'utf8'));
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');if(req.url==='/sandbox')res.end('<iframe title="sandbox" sandbox="allow-scripts" src="/quiz" style="width:100%;height:950px"></iframe>');else if(req.url==='/quiz')res.end(html);else{res.statusCode=404;res.end();}});
async function visible(scope,id){assert(await scope.locator('#'+id).isVisible(),id+' should be visible');}
async function click(scope,id){await scope.locator('#'+id).click();}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,...(process.env.STUDY_TEST_CHROME==='1'?{channel:'chrome'}:{})});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>{errors.push('Unexpected native dialog: '+d.type());d.dismiss();});
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('test: unavailable'))}}));
  await page.goto(base+'/quiz');await visible(page,'welcome');
  await click(page,'start');await page.locator('#options input').nth(0).check();
  await page.locator('[data-page="welcome"]').click();await visible(page,'welcome');
  await click(page,'start');await page.locator('#nav button').nth(0).click();assert(await page.locator('#options input').nth(0).isChecked());
  await page.reload();await visible(page,'welcome');await click(page,'start');await page.locator('#nav button').nth(0).click();assert(await page.locator('#options input').nth(0).isChecked());
  await click(page,'submit');await visible(page,'confirm-panel');assert.match(await page.locator('#confirm-text').textContent(),/4 题未作答/);await click(page,'confirm-no');await visible(page,'work');
  for(let i=0;i<quiz.questions.length;i++){await page.locator('#nav button').nth(i).click();await page.locator('#options input').nth(i===1?(quiz.questions[i].answer[0]+1)%4:quiz.questions[i].answer[0]).check();}
  await click(page,'submit');await click(page,'confirm-yes');await visible(page,'report');assert.match(await page.locator('#score').textContent(),/4.*5/);
  await page.locator('[data-page="plan"]').click();assert((await page.locator('#plan-due').inputValue()).length===10);assert.match(await page.locator('#plan-action').inputValue(),new RegExp(quiz.questions[1].skill));
  await page.locator('#plan-goal').fill('复习细节定位');await click(page,'save-plan');await page.reload();await page.locator('[data-page="plan"]').click();assert.equal(await page.locator('#plan-goal').inputValue(),'复习细节定位');
  await page.locator('[data-page="records"]').click();assert.match(await page.locator('#records-list').textContent(),/4\/5/);await click(page,'resume-record');await click(page,'begin-followup');
  assert.equal(await page.locator('.followup-question').count(),1);const followup=quiz.followups.find(q=>q.target_id===quiz.questions[1].id);await page.locator('.followup-question input').nth(followup.answer[0]).check();
  await page.locator('[data-page="welcome"]').click();await click(page,'start');await visible(page,'followup-work');assert(await page.locator('.followup-question input').nth(followup.answer[0]).isChecked());
  await click(page,'submit-followup');await click(page,'confirm-yes');await visible(page,'followup-result');assert.match(await page.locator('#followup-score').textContent(),/1\/1/);
  const download=page.waitForEvent('download');await click(page,'export-report');assert.match((await download).suggestedFilename(),/^study-record-.*\.json$/);
  await click(page,'copy-prompt');await visible(page,'copy-panel'); // Headless clipboard permission is normally unavailable.
  await click(page,'close-copy');await click(page,'restart');await click(page,'confirm-no');await visible(page,'report');
  await page.locator('[data-page="materials"]').click();assert.match(await page.locator('#material-list').textContent(),new RegExp(quiz.sources[0].title));
  const sandbox=await browser.newPage({viewport:{width:390,height:844}});sandbox.on('pageerror',e=>errors.push(e.message));
  await sandbox.goto(base+'/sandbox');const frame=sandbox.frameLocator('iframe');await click(frame,'start');await click(frame,'submit');await click(frame,'confirm-yes');await visible(frame,'report');await visible(frame,'storage-warning');
  await frame.locator('[data-page="welcome"]').click();await visible(frame,'welcome');await click(frame,'start');await visible(frame,'report');await click(frame,'begin-followup');await click(frame,'submit-followup');await click(frame,'confirm-yes');await visible(frame,'followup-result');
  assert.deepEqual(errors,[]);console.log('PASS: home/resume, refresh, submit/cancel, score, followup, plan persistence, material list, history, export, clipboard fallback, sandbox without modals/storage.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
