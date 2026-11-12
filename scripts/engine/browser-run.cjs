// Fixed browser execution program. The spec cannot supply JavaScript or PASS results.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {captureFonts}=require('./font_capture.cjs');
const [root,specPath,outPath]=process.argv.slice(2);
const skill=path.resolve(__dirname,'../..');
const collector=fs.readFileSync(path.join(skill,'scripts/capture.js'),'utf8');
const load=file=>JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
const taskPath=path.join(root,'work/frontend-policy/task.json');
const task=load(taskPath),spec=load(specPath);
const sha=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');
const inside=name=>{const file=path.resolve(root,name);if(!file.startsWith(path.resolve(root)+path.sep))throw Error('Path escapes project');return file;};
const write=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(value,null,2));};
const supportingFiles=[...(task.project_requirements||[]).flatMap(item=>[item.source,...(item.implementation||[])]),...task.assets.flatMap(item=>[...(item.usage||[]),item.generation_evidence]),...(task.component_libraries?.items||[]).flatMap(item=>[...(item.usage||[]),item.docs_evidence,item.source_evidence]),...Object.values(task.space_effects||{}).filter(item=>item.decision==='used').flatMap(item=>[...(item.usage||[]),item.path,item.generation_evidence])].filter(Boolean);
const buildOutputs=task.deployment?.mode==='build'?(task.checks.find(check=>check.id===task.deployment.check_id)?.outputs||[]):[];
const bindingFiles=buildOutputs.length?buildOutputs:task.files;
const workflowFiles=['reference_gallery','selection_evidence','style_summary','asset_plan','implementation_checklist','checklist_plan','design_document','style_discovery','selected_reference']
 .filter(key=>key!=='implementation_checklist'||!task.checklist_plan).map(key=>task[key]).filter(Boolean);
const coreFiles=[...new Set([...buildOutputs,...Object.values(task.baseline||{}),...task.files,...task.assets.map(x=>x.path),...task.references.map(x=>x.path),...workflowFiles,task.design_plan?.motion_plan?.docs_evidence,task.style_contract?.path,task.component_libraries?.stylekit_priority?.search_evidence,...supportingFiles].filter(Boolean))];
const fingerprints=names=>Object.fromEntries(names.map(name=>[name,sha(fs.readFileSync(inside(name)))]));
const initial=fingerprints(coreFiles);
let playwright;
const userHome=process.env.USERPROFILE||process.env.HOME;
const modulePaths=[root,path.join(process.env.CODEX_HOME||path.join(userHome,'.codex'),'frontend-policy/tooling'),path.join(userHome,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node')];
for(const directory of modulePaths){try{playwright=require(require.resolve('playwright',{paths:[directory]}));break;}catch{}}
if(!playwright)throw Error('Playwright is required. Run scripts/install.py --setup-tools, or install playwright in the project.');
(async()=>{
 let browser;try{browser=await playwright.chromium.launch({headless:true});}catch{browser=await playwright.chromium.launch({channel:'msedge',headless:true});}
 const page=await browser.newPage();
 const userActions=new Set(['click','hover','move_pointer','fill','press','check']);
 const stateProperties=new Set(['text','attribute','value','checked','disabled','visible','url']);
 const scalar=value=>value===null||['string','boolean'].includes(typeof value)||(typeof value==='number'&&Number.isFinite(value));
 const timeoutFor=step=>{
  const value=step.timeout_ms??5000;
  if(!Number.isInteger(value)||value<1||value>15000)throw Error('Assertion timeout_ms must be within 1..15000');
  return value;
 };
 const waitForValue=async(read,matches,step,description)=>{
  const started=Date.now(),timeout=timeoutFor(step);let actual,lastError;
  do{
   try{actual=await read();lastError=null;if(matches(actual))return {actual,elapsed_ms:Date.now()-started};}catch(error){lastError=String(error);}
   if(Date.now()-started>=timeout)break;
   await page.waitForTimeout(Math.min(50,timeout-(Date.now()-started)));
  }while(true);
  throw Error(description+'; actual='+JSON.stringify(actual)+'; elapsed_ms='+(Date.now()-started)+(lastError?'; '+lastError:''));
 };
 const stateDescriptor=step=>{
  if(!stateProperties.has(step.property)||typeof step.name!=='string'||!step.name.trim()||step.name.length>100)throw Error('Invalid state baseline name/property');
  if(step.property!=='url'&&(typeof step.selector!=='string'||!step.selector.trim()))throw Error('State baseline needs a selector');
  if(step.property==='attribute'&&!/^(?:aria-[a-z][a-z0-9-]*|data-[a-z][a-z0-9-]*|open|hidden|disabled|checked|selected|value)$/.test(step.attribute||''))throw Error('Unsupported state attribute');
  return {name:step.name,selector:step.property==='url'?null:step.selector,property:step.property,attribute:step.property==='attribute'?step.attribute:null};
 };
 const readState=async descriptor=>{
  if(descriptor.property==='url')return page.url();
  const locator=page.locator(descriptor.selector),count=await locator.count();
  if(descriptor.property==='visible'&&!count)return false;
  if(count!==1)throw Error('State target must resolve to one element: '+descriptor.selector);
  if(descriptor.property==='checked')return locator.isChecked();
  if(descriptor.property==='disabled')return locator.isDisabled();
  return locator.evaluate((element,{property,attribute})=>{
   if(property==='text')return element.innerText;
   if(property==='attribute')return element.getAttribute(attribute);
   if(property==='value'){
    if(!('value' in element))throw Error('State target has no value');
    return element.value;
   }
   if(property==='visible'){
    if(!element.getClientRects().length)return false;
    const box=element.getBoundingClientRect();if(box.width<=0||box.height<=0)return false;
    let left=box.left,right=box.right,top=box.top,bottom=box.bottom;
    for(let node=element;node;node=node.parentElement||node.getRootNode()?.host){
     const style=getComputedStyle(node);
     if(node.hidden||style.display==='none'||style.contentVisibility==='hidden'||['hidden','collapse'].includes(style.visibility)||Number(style.opacity)===0)return false;
     if(node!==element){
      const clip=node.getBoundingClientRect();
      if(['hidden','clip','scroll','auto'].includes(style.overflowX)){left=Math.max(left,clip.left);right=Math.min(right,clip.right);}
      if(['hidden','clip','scroll','auto'].includes(style.overflowY)){top=Math.max(top,clip.top);bottom=Math.min(bottom,clip.bottom);}
     }
    }
    return right>left&&bottom>top;
   }
   throw Error('Unsupported state property');
  },descriptor);
 };
 const pending=[],runtime={},responseHashes=new Map(),mediaHashes=new Map(),documents=new Map(),runtimeBindings=new Map(),snapshots=[],assertions=[];
 page.on('response',response=>{
  const type=response.request().resourceType();
  const media=type==='image'||type==='font'||Object.values(task.space_effects||{}).some(item=>item.decision==='used'&&item.url===response.url());
  if(response.status()!==200||(!media&&!['document','script','stylesheet'].includes(type)))return;
  pending.push((async()=>{
   const bytes=await response.body(),url=response.url(),hash=sha(bytes);
   if(type==='document'){
    const match=bindingFiles.find(name=>/\.html?$/i.test(name)&&sha(fs.readFileSync(inside(name)))===hash);
    documents.set(url,{url,sha256:hash,source:match||null});return;
   }
   if(media){if(mediaHashes.has(url)&&mediaHashes.get(url)!==hash)throw Error('Media changed during execution: '+url);mediaHashes.set(url,hash);return;}
   if(responseHashes.has(url)&&responseHashes.get(url)!==hash)throw Error('Runtime code changed during browser execution: '+url);
   responseHashes.set(url,hash);
   runtimeBindings.set(url,bindingFiles.find(name=>sha(fs.readFileSync(inside(name)))===hash)||null);
   const name=`work/frontend-policy/evidence/${task.task_id}/runtime/${sha(Buffer.from(url)).slice(0,24)}.txt`;
   const file=inside(name);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,bytes);runtime[url]=name;
  })());
 });
 try{
  const seen=new Set();
  for(const item of spec.cases||[]){
   const key=JSON.stringify([item.page,item.width,item.state]);
   if(seen.has(key)||!task.scope.some(view=>view.page===item.page&&view.width===item.width&&view.state===item.state))throw Error('Unexpected/duplicate browser scope '+key);
   seen.add(key);await page.setViewportSize({width:item.width,height:item.height||844});
   if(item.reduced_motion&&!['reduce','no-preference'].includes(item.reduced_motion))throw Error('Invalid reduced-motion mode');
   await page.emulateMedia({reducedMotion:item.reduced_motion||'no-preference'});
   await page.goto(item.url,{waitUntil:'networkidle',timeout:20000});
   let count=0;const checks=[],remembered=new Map(),rememberedStates=new Map(),stateChanges=[],styleChanges=[],observations=[];
   const steps=item.steps||[];
   for(const [stepIndex,step] of steps.entries()){
    const locator=step.selector?page.locator(step.selector):null;
    switch(step.action){
     case 'click':await locator.click();break;
     case 'hover':await locator.hover();break;
     case 'move_pointer':{
      if(![step.x_ratio,step.y_ratio].every(value=>Number.isFinite(value)&&value>=0&&value<=1))throw Error('Pointer ratios must be within 0..1');
      const box=await locator.boundingBox();if(!box)throw Error('Pointer target has no bounds');
      await page.mouse.move(box.x+box.width*step.x_ratio,box.y+box.height*step.y_ratio);break;
     }
     case 'remember_style':{
      if(!['transform','opacity','filter','boxShadow','backgroundColor','color','borderColor','borderTopColor','outlineColor','outlineWidth'].includes(step.property)||!step.name||remembered.has(step.name))throw Error('Invalid style baseline');
      const value=await locator.evaluate((element,property)=>getComputedStyle(element)[property],step.property);
      remembered.set(step.name,{selector:step.selector,property:step.property,value,step_index:stepIndex});break;
     }
     case 'expect_style_changed':{
      const baseline=remembered.get(step.name);if(!baseline)throw Error('Missing style baseline');
      if((step.selector!==undefined&&step.selector!==baseline.selector)||(step.property!==undefined&&step.property!==baseline.property))throw Error('Changed-style assertion does not match its baseline target');
      const triggers=steps.slice(baseline.step_index+1,stepIndex).filter(action=>userActions.has(action.action));
      if(!triggers.length)throw Error('Changed-style assertion needs an intervening input action');
      const measured=await waitForValue(()=>page.locator(baseline.selector).evaluate((element,property)=>getComputedStyle(element)[property],baseline.property),value=>value!==baseline.value,step,'Style did not change: '+baseline.selector);
      styleChanges.push({name:step.name,selector:baseline.selector,property:baseline.property,before:baseline.value,after:measured.actual,trigger_steps:triggers,elapsed_ms:measured.elapsed_ms,before_step:baseline.step_index,after_step:stepIndex});count++;break;
     }
     case 'expect_style_unchanged':{
      const baseline=remembered.get(step.name);if(!baseline)throw Error('Missing style baseline');
      const stable=await page.evaluate(async({selector,property,value})=>{const start=performance.now();while(performance.now()-start<250){const element=document.querySelector(selector);if(!element||getComputedStyle(element)[property]!==value)return false;await new Promise(requestAnimationFrame);}return true;},baseline);
      if(!stable)throw Error('Style unexpectedly changed: '+baseline.selector);count++;break;
     }
     case 'fill':await locator.fill(step.value);break;
     case 'press':await locator.press(step.key);break;
     case 'check':await locator.check();break;
     case 'remember_state':{
      const descriptor=stateDescriptor(step);
      if(rememberedStates.has(step.name))throw Error('Duplicate state baseline: '+step.name);
      const before=await readState(descriptor);
      if(!scalar(before))throw Error('State baseline must be a scalar value');
      if(Object.hasOwn(step,'value')&&(!scalar(step.value)||before!==step.value))throw Error('Initial state does not match expected value: '+step.name+' actual='+JSON.stringify(before));
      rememberedStates.set(step.name,{...descriptor,before,step_index:stepIndex});break;
     }
     case 'expect_state_changed':{
      const baseline=rememberedStates.get(step.name);if(!baseline)throw Error('Missing state baseline: '+step.name);
      if((step.selector!==undefined&&step.selector!==baseline.selector)||(step.property!==undefined&&step.property!==baseline.property)||(step.attribute!==undefined&&step.attribute!==baseline.attribute))throw Error('Changed-state assertion does not match its baseline target');
      const triggers=steps.slice(baseline.step_index+1,stepIndex).filter(action=>userActions.has(action.action));
      if(!triggers.length)throw Error('Changed-state assertion needs an intervening input action');
      const hasExpected=Object.hasOwn(step,'value');
      if(hasExpected&&(!scalar(step.value)||step.value===baseline.before))throw Error('Expected changed state must differ from its baseline');
      const measured=await waitForValue(()=>readState(baseline),value=>scalar(value)&&value!==baseline.before&&(!hasExpected||value===step.value),step,'State did not change as expected: '+step.name+(hasExpected?' expected='+JSON.stringify(step.value):''));
      stateChanges.push({name:baseline.name,selector:baseline.selector,property:baseline.property,attribute:baseline.attribute,before:baseline.before,after:measured.actual,trigger_steps:triggers,elapsed_ms:measured.elapsed_ms,before_step:baseline.step_index,after_step:stepIndex});
      count++;break;
     }
     case 'expect_visible':await waitForValue(()=>readState({selector:step.selector,property:'visible'}),value=>value===true,step,'Element not visibly painted: '+step.selector);count++;break;
     case 'expect_hidden':await waitForValue(()=>readState({selector:step.selector,property:'visible'}),value=>value===false,step,'Element remains visible: '+step.selector);count++;break;
     case 'expect_css_number':{
      if(!['fontSize','fontWeight','lineHeight','width','height'].includes(step.property))throw Error('Unsupported numeric CSS property');
      const value=await locator.evaluate((element,property)=>parseFloat(getComputedStyle(element)[property]),step.property);
      if(!Number.isFinite(value)||(!Number.isFinite(step.min)&&!Number.isFinite(step.max))||(Number.isFinite(step.min)&&value<step.min)||(Number.isFinite(step.max)&&value>step.max))throw Error('Numeric CSS assertion failed: '+step.selector+' actual='+value);
      count++;break;
     }
     case 'expect_area_ratio':{
      if(!['viewport','parent'].includes(step.basis)||!['area','height','width'].includes(step.measure))throw Error('Unsupported area-ratio basis/measure');
      const value=await locator.evaluate((element,options)=>{const a=element.getBoundingClientRect(),b=options.basis==='parent'?element.parentElement.getBoundingClientRect():{width:innerWidth,height:innerHeight};return options.measure==='area'?a.width*a.height/(b.width*b.height):a[options.measure]/b[options.measure];},{basis:step.basis,measure:step.measure});
      if(!Number.isFinite(value)||(!Number.isFinite(step.min)&&!Number.isFinite(step.max))||(Number.isFinite(step.min)&&value<step.min)||(Number.isFinite(step.max)&&value>step.max))throw Error('Area-ratio assertion failed: '+step.selector+' actual='+value);
      count++;break;
     }
     case 'expect_in_viewport':{
      const box=await locator.boundingBox(),view=page.viewportSize();
      if(!box||box.x<0||box.y<0||box.x+box.width>view.width+1||box.y+box.height>view.height+1)throw Error('Viewport assertion failed: '+step.selector);
      count++;break;
     }
     case 'expect_text':{
      const measured=await waitForValue(()=>locator.innerText({timeout:timeoutFor(step)}),value=>value===step.value,step,'Text assertion failed: '+step.selector+' expected='+JSON.stringify(step.value));
      observations.push({action:step.action,selector:step.selector,expected:step.value,actual:measured.actual,elapsed_ms:measured.elapsed_ms});count++;break;
     }
     case 'expect_url':{
      const measured=await waitForValue(async()=>page.url(),value=>value===step.value,step,'URL assertion failed; expected='+JSON.stringify(step.value));
      observations.push({action:step.action,expected:step.value,actual:measured.actual,elapsed_ms:measured.elapsed_ms});count++;break;
     }
     default:throw Error('Unsupported declarative action '+step.action);
    }
    if(step.action.startsWith('expect_'))checks.push({...step});
   }
   if(!count)throw Error('Each declared state requires an actual assertion');
   await Promise.all(pending);
   const navigationURL=await page.evaluate(()=>performance.getEntriesByType('navigation')[0]?.name||location.href.split('#')[0]);
   const documentSource=documents.get(page.url())||documents.get(navigationURL)||documents.get(page.url().split('#')[0]);
   if(!documentSource?.source)throw Error('Served HTML does not match declared current source/build output: '+page.url());
   const region=task.scope.find(view=>view.page===item.page&&view.width===item.width&&view.state===item.state)?.root_selector||'body';
   const assetSelectors=[...new Set((task.assets||[]).map(asset=>asset.render_check).filter(check=>check&&['page','width','state'].every(key=>check[key]===item[key])).map(check=>check.selector).filter(Boolean))];
   const fontsReady=await page.evaluate(()=>Promise.race([document.fonts.ready.then(()=>true),new Promise(resolve=>setTimeout(()=>resolve(false),5000))]));
   const snapshot=await page.evaluate(collector.replace("const ROOT_SELECTOR = 'body';",'const ROOT_SELECTOR = '+JSON.stringify(region)+';').replace('const ASSET_SELECTORS = [];','const ASSET_SELECTORS = '+JSON.stringify(assetSelectors)+';'));
   snapshot.body_typography=await captureFonts(page,snapshot,fontsReady);
   for(const resource of snapshot.resources){
    if(new URL(resource.url).origin===new URL(documentSource.url).origin&&!runtimeBindings.get(resource.url))throw Error('Served runtime does not match declared current source/build output: '+resource.url);
   }
   const stem=`work/frontend-policy/evidence/${task.task_id}/browser/${snapshots.length}`;
   await page.screenshot({path:inside(stem+'.png'),fullPage:true});
   Object.assign(snapshot,{page:item.page,state:item.state,screenshot:stem+'.png',document_source:documentSource,media_responses:[...mediaHashes].map(([url,sha256])=>({url,sha256}))});
   if(task.level!=='L3'&&!['body','html'].includes(region)){
    snapshot.region_screenshot=stem+'.region.png';
    await page.locator(region).screenshot({path:inside(snapshot.region_screenshot)});
   }
   snapshots.push({path:stem+'.json',snapshot});assertions.push({page:item.page,width:item.width,state:item.state,passed:count,checks,steps,state_changes:stateChanges,style_changes:styleChanges,observations});
  }
  if(!snapshots.length)throw Error('No browser cases executed');
  await Promise.all(pending);
  if(JSON.stringify(initial)!==JSON.stringify(fingerprints(coreFiles)))throw Error('Application sources/assets changed during browser execution');
  task.runtime_sources=runtime;write(taskPath,task);
  const names=[...new Set([...coreFiles,...Object.values(runtime)])],hashes=fingerprints(names);
  for(const item of snapshots){item.snapshot.source_hashes=hashes;write(inside(item.path),item.snapshot);}
  write(outPath,{captures:snapshots.map(x=>x.path),assertions,pid:process.pid,runner:'fixed-browser-process'});
 }catch(error){
  const failure=`work/frontend-policy/evidence/${task.task_id}/browser/failure.png`;
  fs.mkdirSync(path.dirname(inside(failure)),{recursive:true});
  await page.screenshot({path:inside(failure),fullPage:true}).catch(()=>{});
  write(outPath,{diagnostic_screenshot:fs.existsSync(inside(failure))?failure:null,error:String(error)});
  throw error;
 }finally{await browser.close();}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
