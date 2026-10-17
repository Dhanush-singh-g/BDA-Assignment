// Optional browser regression: requires Node, Playwright and a Chromium browser.
// Launches an isolated Flask fixture; intercepts jobs so no real analysis starts.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const {once} = require('node:events');
const readline = require('node:readline');

(async () => {
  const server = spawn('.venv/bin/python', ['-u', '-c', `
import tempfile
from fdc.dashboard import create_app
from werkzeug.serving import make_server
with tempfile.TemporaryDirectory() as root:
    server = make_server('127.0.0.1', 0, create_app(root))
    print(server.server_port, flush=True)
    server.serve_forever()
`], {stdio: ['ignore', 'pipe', 'pipe']});
  let browser;
  try {
    const lines = readline.createInterface({input: server.stdout});
    const port = (await once(lines, 'line'))[0];
    browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
    const page = await browser.newPage();
    const errors = [], logRequests = [];
    page.on('pageerror', e => errors.push(e.message));
    const old = {id:'a'.repeat(32),status:'succeeded',spec:{action:'workflow',foods:50000},created_at:'2026-01-01T00:00:00Z',stages:[{name:'Run and reconcile MapReduce, Pig and Hive',status:'passed'}],result:'data/realdev_123',hive_progress:{completed:8,expected:8},themes:[]};
    let jobs = [old];
    await page.route('**/api/control/jobs', async route => {
      if (route.request().method() === 'POST') {
        assert.deepEqual(route.request().postDataJSON(),{action:'workflow',foods:50000});
        jobs = [{id:'b'.repeat(32),status:'queued',spec:{action:'workflow',foods:50000},created_at:new Date().toISOString(),stages:[],themes:[]},old];
        return route.fulfill({status:202,json:jobs[0]});
      }
      return route.fulfill({json:{jobs,exports:{},full_archive_available:true}});
    });
    await page.route('**/api/control/jobs/*/log', route => {
      const id = route.request().url().split('/').at(-2);
      logRequests.push(id);
      return route.fulfill({json:{log:id===old.id?'OLD SAVED LOG':'CURRENT RUN OUTPUT'}});
    });
    const waitText = async (selector, text) => page.waitForFunction(({selector,text}) => document.querySelector(selector)?.textContent.includes(text),{selector,text});
    await page.goto('http://127.0.0.1:'+port);
    await page.click('#analysis-tab');
    await waitText('#job-summary','Ready. No current analysis.');
    assert.equal(await page.locator('#job-stages li').count(),0);
    assert.equal(await page.locator('#job-choice').inputValue(),'');
    assert.equal(await page.locator('#current-process').isVisible(),false);
    assert.deepEqual(logRequests,[],'Idle page must never fetch old logs');

    await page.selectOption('#job-choice',old.id);
    await waitText('#job-summary','Saved status: succeeded');
    await waitText('#job-log','OLD SAVED LOG');
    assert.equal(await page.locator('#history-note').isVisible(),true);
    await page.click('#current-job');
    await waitText('#job-summary','Ready. No current analysis.');
    assert.equal(await page.locator('#job-log').textContent().then(x=>x.includes('OLD SAVED LOG')),false);

    await page.click('#new-job button');
    await waitText('#job-summary','Current run: queued');
    await waitText('#job-log','CURRENT RUN OUTPUT');
    const current = jobs[0];
    Object.assign(current,{status:'running',stages:[{name:'Run and reconcile MapReduce, Pig and Hive',status:'running'}],live:{stage:'Identical queries / performance',started_at:new Date(Date.now()-65000).toISOString(),checked_at:new Date().toISOString(),operation:{label:'Execute benchmark',pid:1234},last_output:{file:'query.log',text:'Map 50% Reduce 0%',at:new Date().toISOString()}},hive_progress:{completed:2,expected:8,current:{number:3,total:8,query:'protein_summary',table:'nutrients_text',warmup:true}}});
    await waitText('#process-stage','Identical queries / performance');
    await waitText('#process-operation','Hive query 3/8: protein_summary');
    await waitText('#process-time','Process ID: 1234');
    await waitText('#process-output','Map 50% Reduce 0%');
    assert.equal(await page.locator('#new-job button').isDisabled(),true);
    await page.reload();
    await page.click('#analysis-tab');
    await waitText('#job-summary','Current run: running');
    await waitText('#process-output','Map 50% Reduce 0%');

    Object.assign(current,{status:'succeeded',result:'data/realdev_456',live:null,hive_progress:{completed:8,expected:8}});
    await waitText('#job-summary','Current run: succeeded');
    assert.equal(await page.locator('#current-process').isVisible(),false);
    await page.reload();
    await page.click('#analysis-tab');
    await waitText('#job-summary','Ready. No current analysis.');
    assert.equal(await page.locator('#job-stages li').count(),0);
    assert.equal((await page.locator('#job-log').textContent()).includes('CURRENT RUN OUTPUT'),false);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.deepEqual(errors,[]);
    console.log('Browser checks passed: fresh idle, explicit history, clearing logs, new run, live operation/query/output, active reload, completed reload, mobile layout.');
  } finally {
    if(browser) await browser.close();
    server.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
