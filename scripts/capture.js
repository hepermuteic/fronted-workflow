// Execute this read-only expression in the actual application and state.
// For component-only work, change ROOT_SELECTOR to its real enclosing region.
(() => {
  const ROOT_SELECTOR = 'body';
  const ASSET_SELECTORS = [];
  const root = document.querySelector(ROOT_SELECTOR);
  if (!root) throw new Error('Capture region not found');
  const paint = element => {
    const box=element.getBoundingClientRect(),style=getComputedStyle(element);
    let left=box.left,right=box.right,top=box.top,bottom=box.bottom,opacity=1;
    let displayed=element.getClientRects().length>0&&!['hidden','collapse'].includes(style.visibility);
    for(let node=element;node;node=node.parentElement||node.getRootNode()?.host){
      const current=getComputedStyle(node);opacity*=Number(current.opacity);
      if(node.hidden||current.display==='none'||current.contentVisibility==='hidden')displayed=false;
      if(node!==element){
        const clip=node.getBoundingClientRect();
        if(['hidden','clip','scroll','auto'].includes(current.overflowX)){left=Math.max(left,clip.left);right=Math.min(right,clip.right);}
        if(['hidden','clip','scroll','auto'].includes(current.overflowY)){top=Math.max(top,clip.top);bottom=Math.min(bottom,clip.bottom);}
      }
    }
    // Full-page screenshots include below-fold content, but not material entirely
    // outside the document or clipped out of a scroll container.
    left=Math.max(left,-scrollX);right=Math.min(right,innerWidth-scrollX);
    top=Math.max(top,-scrollY);bottom=Math.min(bottom,Math.max(document.documentElement.scrollHeight,document.body?.scrollHeight||0,innerHeight)-scrollY);
    const width=Math.max(0,right-left),height=Math.max(0,bottom-top);
    return {visible:displayed&&opacity>0&&width>0&&height>0,effective_opacity:opacity,visible_rect:{x:left,y:top,width,height}};
  };
  const visible = element => paint(element).visible;
  const label = element => element.id ? '#' + element.id : element.tagName.toLowerCase();
  const roots = [root];
  const elements = [];
  const shadow_html = [];
  const pseudoText=(element,pseudo)=>{
    const style=getComputedStyle(element,pseudo),content=style.content;
    if(style.display==='none'||style.visibility==='hidden'||!content||['none','normal','""'].includes(content)||!content.startsWith('"'))return '';
    try{return JSON.parse(content);}catch{return content.replace(/^"|"$/g,'').replace(/\\a\s?/gi,' ');}
  };
  const cloneVisible = element => {
    const copy = element.cloneNode(true);
    const originals = [element, ...element.querySelectorAll('*')];
    const copies = [copy, ...copy.querySelectorAll('*')];
    for (let i = 0; i < originals.length; i++) {
      if (!visible(originals[i]) || originals[i].matches('script,style,template,noscript,svg')) {copies[i].remove();continue;}
      const before=pseudoText(originals[i],'::before'),after=pseudoText(originals[i],'::after');
      if(before)copies[i].insertBefore(document.createTextNode(before),copies[i].firstChild);
      if(after)copies[i].appendChild(document.createTextNode(after));
    }
    return copy.outerHTML;
  };
  for (let index = 0; index < roots.length; index++) {
    const current = roots[index];
    const nodes = current instanceof Element ? [current, ...current.querySelectorAll('*')] : [...current.querySelectorAll('*')];
    for (const element of nodes) {
      if (!visible(element)) continue;
      elements.push(element);
      if (element.shadowRoot) {
        roots.push(element.shadowRoot);
        const fragment = document.createElement('div');
        for (const child of element.shadowRoot.children) if (visible(child) && !child.matches('style,script')) fragment.insertAdjacentHTML('beforeend', cloneVisible(child));
        shadow_html.push({host:label(element),html:fragment.innerHTML});
      }
    }
  }
  const styles = elements.map(element => {
    const style = getComputedStyle(element);
    return {selector:label(element),color:style.color,backgroundColor:style.backgroundColor,backgroundImage:style.backgroundImage,fontSize:style.fontSize,fontFamily:style.fontFamily};
  });
  const cssPath = element => {
    const parts = [];
    for (let node = element; node instanceof Element; node = node.parentElement) {
      const siblings = node.parentNode ? [...node.parentNode.children].filter(item => item.tagName === node.tagName) : [node];
      parts.unshift(node.tagName.toLowerCase() + ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')');
    }
    return parts.join(' > ');
  };
  const body_text_samples = [];
  for (const element of elements) {
    let display = false;
    for (let node = element; node; node = node.getRootNode().host) {
      if (node.closest('h1,h2,h3,h4,h5,h6,[role="heading"],script,style,template,noscript,svg,code,pre')) { display = true; break; }
    }
    if (display) continue;
    const direct = [...element.childNodes].filter(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()).map(node => node.textContent.trim());
    const control = element.matches('input,textarea,select') ? (element.value || element.placeholder || '') : '';
    const hosts = [];
    for (let boundary = element.getRootNode(); boundary instanceof ShadowRoot; boundary = boundary.host.getRootNode()) hosts.unshift(cssPath(boundary.host));
    const addSample = (text, pseudo = null) => {
      const style = getComputedStyle(element, pseudo ? '::' + pseudo : null);
      body_text_samples.push({selector:label(element) + (pseudo ? '::' + pseudo : ''),css_path:cssPath(element),shadow_hosts:hosts,
        text:text.slice(0,500),direct_text:pseudo ? [] : direct,pseudo,font_family:style.fontFamily,font_size:style.fontSize,font_weight:style.fontWeight,line_height:style.lineHeight});
    };
    if (direct.length || control.trim()) addSample(direct.join(' ') || control);
    for (const pseudo of ['before','after']) {
      const text = pseudoText(element,'::' + pseudo);
      if (text.trim()) addSample(text,pseudo);
    }
  }
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
  const colorContext=canvas.getContext('2d',{willReadFrequently:true});
  const normalized_colors=[],generated_text=[],material_candidates=[],rejected_material_layers=[];
  const colorTokens=value=>value.match(/#[0-9a-f]{3,8}\b|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^)]*\)|\b[a-z]+\b/gi)||[];
  const rgbaOf=token=>{
    if(!CSS.supports('color',token)||['currentcolor','inherit','initial','unset','none'].includes(token.toLowerCase()))return null;
    colorContext.clearRect(0,0,1,1);colorContext.fillStyle=token;colorContext.fillRect(0,0,1,1);
    return Array.from(colorContext.getImageData(0,0,1,1).data);
  };
  const backgroundLayers=value=>{
    const layers=[];let start=0,depth=0,quote=null;
    for(let i=0;i<value.length;i++){
      const char=value[i];
      if(quote){if(char==='\\')i++;else if(char===quote)quote=null;continue;}
      if(char==='"'||char==="'"){quote=char;continue;}
      if(char==='(')depth++;else if(char===')')depth--;else if(char===','&&!depth){layers.push(value.slice(start,i).trim());start=i+1;}
    }
    layers.push(value.slice(start).trim());return layers;
  };
  const inspectStyle=(element,pseudo=null)=>{
    const style=getComputedStyle(element,pseudo),selector=label(element)+(pseudo||'');
    if(pseudo&&(!style.content||['none','normal'].includes(style.content)||style.display==='none'||['hidden','collapse'].includes(style.visibility)))return;
    const painted=paint(element),opacity=painted.effective_opacity*(pseudo?Number(style.opacity):1);
    if(!painted.visible||opacity<=0)return;
    if(style.backgroundImage!=='none'&&(element===root||painted.visible_rect.width*painted.visible_rect.height>=innerWidth*innerHeight*.25)){
      for(const layer of backgroundLayers(style.backgroundImage)){
        let reason=null;
        if(/^(?:repeating-)?(?:linear|radial|conic)-gradient\(/i.test(layer)){
          const colors=colorTokens(layer).map(rgbaOf).filter(Boolean);
          if(colors.length>=2&&colors.every(color=>color[3]===0))reason='transparent_gradient';
          else if(colors.length>=2&&colors.every(color=>color.every((value,index)=>value===colors[0][index])))reason='constant_gradient';
        }
        const entry={selector,background:layer,effective_opacity:opacity,visible_rect:painted.visible_rect,visible:true};
        if(reason)rejected_material_layers.push({...entry,reason});
        else material_candidates.push({...entry,qualification:'Candidate only; inspect actual material and reference fidelity'});
      }
    }
    for(const property of ['color','backgroundColor','borderTopColor','borderRightColor','borderBottomColor','borderLeftColor','outlineColor','textDecorationColor','fill','stroke','backgroundImage','boxShadow','textShadow']){
      // Non-painting border/outline defaults cannot introduce a visible color.
      if(property.startsWith('border')){const side=property.replace('Color','');if(!parseFloat(style[side+'Width'])||style[side+'Style']==='none')continue;}
      if(property==='outlineColor'&&(!parseFloat(style.outlineWidth)||style.outlineStyle==='none'))continue;
      if(property==='textDecorationColor'&&style.textDecorationLine==='none')continue;
      for(const token of colorTokens(style[property]||'')){
        const rgba=rgbaOf(token);if(!rgba)continue;
        if(rgba[3])normalized_colors.push({selector,property,value:`rgba(${rgba[0]},${rgba[1]},${rgba[2]},${rgba[3]/255})`});
      }
    }
    if(pseudo&&style.content&&style.content!=='none'){
      generated_text.push({selector,text:pseudoText(element,pseudo),functional:element.matches('button,a,[role="button"],[data-functional-icon]')});
    }
  };
  for(const element of elements){inspectStyle(element);inspectStyle(element,'::before');inspectStyle(element,'::after');}
  const animations = [];
  for (const element of elements) {
    const style = getComputedStyle(element);
    if (style.transitionDuration.split(',').some(value=>parseFloat(value)>0)) for (const easing of style.transitionTimingFunction.split(/,(?![^()]*\))/)) animations.push({selector:label(element),easing:easing.trim()});
    if (style.animationName!=='none') for(const easing of style.animationTimingFunction.split(/,(?![^()]*\))/)) animations.push({selector:label(element),easing:easing.trim()});
  }
  for(const animation of document.getAnimations()){
    const effect=animation.effect;if(!effect)continue;
    const target=effect.target;const selector=target instanceof Element?label(target):'web-animation';
    const overall=effect.getTiming().easing,frames=effect.getKeyframes().slice(0,-1);
    // CSS Animation effects commonly have linear outer timing but non-linear
    // keyframe easing. Inspect actual segments, not the neutral wrapper alone.
    if(overall!=='linear'||!frames.length)animations.push({selector,easing:overall,source:'web-animation'});
    for(const frame of frames)if(frame.easing&&(overall==='linear'||frame.easing!=='linear'))animations.push({selector,easing:frame.easing,source:'keyframe'});
  }
  const resources = new Map();
  const add = (url,kind) => {if(url&&!url.startsWith('data:'))resources.set(url,{url,kind});};
  for(const script of document.scripts)add(script.src,'script');
  for(const sheet of document.styleSheets)add(sheet.href,'stylesheet');
  for(const resource of performance.getEntriesByType('resource'))if(resource.initiatorType==='script'||(resource.initiatorType==='css'&&/\.css(?:[?#]|$)/i.test(resource.name)))add(resource.name,'runtime');
  const images = elements.filter(element=>element instanceof HTMLImageElement).map(image=>({selector:label(image),selectors:ASSET_SELECTORS.filter(selector=>image.matches(selector)),url:image.currentSrc||image.src,loaded:image.complete&&image.naturalWidth>0,width:image.getBoundingClientRect().width,height:image.getBoundingClientRect().height,...paint(image)}));
  const rect = element => {const box=element.getBoundingClientRect();return {selector:label(element),tag:element.tagName.toLowerCase(),x:box.x,y:box.y,width:box.width,height:box.height};};
  const layout_regions=elements.filter(element=>element.matches('main,section,article,nav,header,footer,[data-layout-region]')||(['grid','flex'].includes(getComputedStyle(element).display)&&element.children.length>1)).map(element=>({
    ...rect(element),display:getComputedStyle(element).display,columns:getComputedStyle(element).gridTemplateColumns,
    children:[...element.children].filter(visible).map(rect)
  }));
  return {schema:'frontend-policy/browser-v1',url:location.href,captured_at:new Date().toISOString(),root_selector:ROOT_SELECTOR,
    page:null,state:null,screenshot:null,source_hashes:null,viewport:{width:innerWidth,height:innerHeight},
    horizontal_overflow:document.documentElement.scrollWidth>innerWidth+1,html:cloneVisible(root),shadow_html,styles,animations,
    collector_version:4,body_text_samples,resources:[...resources.values()],images,layout_regions,normalized_colors,generated_text,surface:{scope:root===document.body||root===document.documentElement?'document':'region',material_candidates,rejected_material_layers},
    functional_icons:[...elements.filter(element=>element.matches('[data-functional-icon],button,a,[role="button"],input[type="submit"],input[type="button"]')).map(element=>element.textContent||element.value),...generated_text.filter(item=>item.functional).map(item=>item.text)],
    boundaries:{iframes:[...document.querySelectorAll('iframe')].map(frame=>frame.src),possible_closed_roots:elements.filter(element=>element.tagName.includes('-')&&!element.shadowRoot).map(label)}};
})()
