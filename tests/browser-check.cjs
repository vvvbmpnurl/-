const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
(async()=>{
 const service=spawn('python3',['server.py'],{env:{...process.env,FACTORY_PORT:'18766',FACTORY_DB:'/tmp/factory-browser-'+process.pid+'.db'}});
 let browser;
 try {
  await new Promise((resolve,reject)=>{service.stdout.once('data',resolve);service.once('error',reject);service.once('exit',code=>reject(Error('server exit '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',err=>errors.push(err.message));
  await page.goto('http://127.0.0.1:18766');
  await page.waitForSelector('#cfJobs',{state:'attached'});
  await page.evaluate(()=>{setPort('media');document.querySelector('#nav [data-p="p4"]').click();});
  assert.match(await page.locator('#cfWorkspace').innerText(),/未配置/);
  assert(await page.locator('[data-action="create"]').isDisabled());
  // Create existing copy through the original UI, then verify import into video workflow.
  await page.evaluate(()=>{curPlat='dy';renderTopics();document.querySelectorAll('.tbox').forEach((x,i)=>x.checked=i===0);genOutputs();});
  await page.waitForFunction(()=>document.querySelector('#cfSource').options.length>1,{},{timeout:10000});
  await page.locator('#cfSource').selectOption({index:1});
  assert((await page.locator('#cfTitle').inputValue()).length>0);
  assert((await page.locator('#cfScript').inputValue()).length>0);
  const demo={id:'demo',title:'审核示例',script:'口播稿',provider:'domestic',status:'ready',created:Date.now()/1000,video_url:'https://example.com/video.mp4',review:null};
  const fake={csrf:'test',jobs:[demo],deliveries:[],accounts:[{id:'a',name:'门店A',platform:'dy'}],providers:[{id:'domestic',name:'国内数字人',ready:true}],publish_ready:true};
  await page.route('**/api/factory/**',async route=>{
   const url=route.request().url();
   if(url.endsWith('/review')){
    const data=route.request().postDataJSON();
    if(!data.watched&&data.decision==='approved')return route.fulfill({status:400,json:{error:'请先确认已观看成片'}});
    demo.review=data;
   }
   if(url.endsWith('/publish')) fake.deliveries=[{id:'d',job:'demo',account:'a',account_name:'门店A',status:'submitted',remote_id:'r'}];
   return route.fulfill({json:url.endsWith('/state')?fake:{ok:true}});
  });
  await page.locator('[data-action="reload"]').click();
  await page.waitForSelector('.cf-watched');
  await page.locator('[data-action="approve"]').click();
  await page.waitForFunction(()=>document.querySelector('#cfFeedback').textContent.includes('请先确认'));
  await page.locator('.cf-watched').check();
  await page.locator('[data-action="approve"]').click();
  await page.waitForSelector('.cf-account');
  await page.locator('.cf-account').check();
  await page.locator('[data-action="publish"]').click();
  await page.waitForFunction(()=>document.querySelector('#cfDeliveries').textContent.includes('平台已受理'));
  assert(!await page.locator('#cfDeliveries').innerText().then(x=>x.includes('已发布')));
  await page.setViewportSize({width:760,height:1000});
  const dims=await page.locator('#cfWorkspace').evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth}));
  assert(dims.scroll<=dims.client+1,JSON.stringify(dims));
  assert.deepEqual(errors,[]);
  console.log('Browser checks passed: original-topic import, config gating, review gate, distribution receipt, responsive workspace, no JS errors.');
 } finally {if(browser)await browser.close();service.kill();}
})().catch(err=>{console.error(err);process.exitCode=1;});
