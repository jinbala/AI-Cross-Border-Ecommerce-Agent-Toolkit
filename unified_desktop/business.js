(() => {
  'use strict';
  const root = document.getElementById('business-root');
  const host = globalThis.PANTS_DESKTOP && globalThis.chrome?.webview;
  document.getElementById('desktop-update').insertAdjacentHTML('afterbegin','<div class="section-heading"><h2>采集设置</h2><p>选择从罗盘读取的范围</p></div>');
  document.getElementById('filter-panel').insertAdjacentHTML('afterbegin','<div class="section-heading"><h2>筛选条件</h2><p>从已有榜单中挑款</p></div>');
  document.getElementById('source').closest('section').classList.add('data-summary');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const requests = new Map();
  let state, page = '', productId = '', experimentId = '', artifactId = '', report = '', workflowPrompt = '', workflowResult = '';
  let pricingResult = null, candidateBrief = '', selectedCandidate = '', renderId = 0;
  const drafts = {};
  const money = value => Number(value).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2});
  const today = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const view = () => document.getElementById('biz-content');
  const message = (value, error=false) => {
    const target = document.getElementById('biz-message'); target.textContent = value; target.className = 'biz-message' + (error ? ' error' : ''); target.hidden = !value;
  };
  const btn = (action, title, primary=false, extra='') => `<button type="button" data-action="${esc(action)}" ${extra} class="${primary ? 'primary' : ''}">${esc(title)}</button>`;
  const options = (items, selected) => items.map(([value,label]) => `<option value="${esc(value)}" ${String(value)===String(selected)?'selected':''}>${esc(label)}</option>`).join('');
  const productOptions = selected => options([['','不关联产品'], ...(state?.products || []).map(p=>[p.id,(p.is_demo?'【演示】':'')+p.name])], selected);
  const input = (key,title,value='',type='text',wide=false) => `<label class="${wide?'wide':''}">${esc(title)}<input name="${esc(key)}" type="${type}" value="${esc(value)}" ${type==='number'?'min="0" step="any"':''}></label>`;
  const textarea = (key,title,value='',wide=true) => `<label class="${wide?'wide':''}">${esc(title)}<textarea name="${esc(key)}">${esc(value)}</textarea></label>`;
  const select = (key,title,items,value='',wide=false) => `<label class="${wide?'wide':''}">${esc(title)}<select name="${esc(key)}">${options(items,value)}</select></label>`;
  const head = (title,subtitle,actions='') => `<div class="biz-head"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${actions}</div>`;
  const output = value => `<pre class="biz-output" tabindex="0">${esc(value)}</pre>`;
  const empty = title => `<div class="biz-empty">${esc(title)}</div>`;
  const form = () => Object.fromEntries([...view().querySelectorAll('[name]')].filter(w=>w.type!=='checkbox'||w.checked).map(w=>[w.name,w.type==='checkbox'?true:w.value]));
  const activeProduct = () => state?.products.find(p=>p.id===productId);
  function call(command,args={}) {
    if (!host) return Promise.reject(new Error('请在整合桌面版中使用经营功能。'));
    const id = crypto.randomUUID();
    return new Promise((resolve,reject) => {
      const timer = setTimeout(()=>{requests.delete(id);reject(new Error('本次处理超时，请稍后重试。'));},190000);
      requests.set(id,{resolve,reject,timer}); host.postMessage({action:'business',id,command,args});
    });
  }
  function receive(response) {
    const request = requests.get(response.id); if(!request) return;
    clearTimeout(request.timer); requests.delete(response.id);
    if(response.ok) request.resolve(response.data); else request.reject(new Error(response.error || '本次操作未完成。'));
  }
  function captureDraft() {
    if (!page || !view().querySelector('[name]')) return;
    const value = form(); delete value.api_key;
    drafts[page+':'+(page==='products'?productId:page==='experiments'?experimentId:'')] = value;
  }
  async function refresh() { state = await call('state'); return state; }
  async function navigate(next, selected='') {
    captureDraft(); page = next; if(selected && next==='products') productId=selected;
    host?.postMessage({action:'business-navigation',section:next==='intake'?'candidates':next});
    document.body.dataset.business='true'; root.hidden=false; message('');
    const request = ++renderId; view().innerHTML='<div class="biz-loading">正在读取本机资料…</div>';
    try { await refresh(); if(request===renderId) render(); } catch(error) {message(error.message,true);}
  }
  function showPants() {captureDraft();page='';renderId++;root.hidden=true;delete document.body.dataset.business;}
  function render() {
    const routes={candidates:renderCandidates,products:renderProducts,pricing:renderPricing,workflows:renderWorkflows,experiments:renderExperiments,artifacts:renderArtifacts,settings:renderSettings,analytics:renderAnalytics};
    (routes[page]||renderCandidates)();
  }
  function renderCandidates() {
    const rows=state.candidates;
    view().innerHTML=head('我的候选','罗盘收藏与手工线索汇总在这里，选中后可以直接建档算利润。',btn('intake','添加线索',true))
      +'<div class="biz-tools"><input id="biz-search" type="search" placeholder="搜索款式 / 商品 ID" style="max-width:330px">'+btn('sync-favorites','同步当前榜单收藏')+btn('open-screen','表格与条件初筛')+'</div>'
      +`<div class="biz-table-wrap"><table class="biz-table"><thead><tr><th>款式 / 商品</th><th>来源</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows.map(c=>`<tr data-search="${esc((c.name+' '+c.source_id).toLowerCase())}"><td>${esc(c.name)} ${c.evidence?.is_demo?'<span class="biz-tag demo">演示</span>':''}<div class="hint">${esc(c.source_id)}</div></td><td>${esc(c.platform)}<div class="hint">${esc(c.as_of||'日期待补')}</div></td><td><span class="biz-tag">${esc(c.review_status)}</span><div class="hint">${esc(c.status)}</div></td><td>${btn('candidate-cost','建档算利润',true,`data-id="${esc(c.id)}"`)} ${btn('candidate-ai','调研',false,`data-id="${esc(c.id)}"`)} ${btn('candidate-detail','资料',false,`data-id="${esc(c.id)}"`)}</td></tr>`).join('')}</tbody></table>${rows.length?'':empty('还没有候选。在“选品找款”收藏一款，或点击“添加线索”。')}</div><div id="biz-detail"></div>`;
  }
  function renderProducts() {
    const p=drafts['products:'+productId] || activeProduct() || {};
    const primary=state.fields.slice(0,12), long=state.fields.slice(12);
    view().innerHTML=head('产品档案','来源资料自动带入，补充本厂真实面料、尺码、成本和交期。')
      +`<div class="biz-tools"><select id="biz-product-picker" class="biz-select">${productOptions(productId)}</select>${btn('new-product','新建档案')}</div>`
      +'<div class="biz-panel"><div class="biz-form">'+primary.map(([key,title])=>input(key,title,p[key]||'')).join('')
      +`<details class="wide"><summary>尺码、品控、卖点与完整来源资料</summary><div class="biz-form">${long.map(([key,title])=>textarea(key,title,p[key]||'')).join('')}</div></details></div></div>`
      +'<div class="biz-section-actions">'+btn('save-product','保存档案',true)+btn('product-cost','保存并算利润')+btn('product-ai','保存并准备文案')+'</div>';
  }
  function renderPricing() {
    const p=activeProduct() || {}, d=drafts['pricing:'] || {};
    const values={mode:'供货 / 批发',currency:'CNY',price:p.supply_price||'',production:p.cost||'',packaging:0,inbound:0,shipping:0,other:0,loss:0,commission:0,tax:0,advertising:0,target:20,quantity:1,...d};
    view().innerHTML=head('报价与利润','填写你实际能收到的单件收入，以及同一币种的真实成本。')
      +`<div class="biz-tools"><select id="biz-pricing-product" class="biz-select">${productOptions(productId)}</select></div>`
      +(p.is_demo?'<div class="biz-note">当前为演示款，仅供试用。保存的利润报告会标为演示，不作为真实经营结果。</div>':'')
      +(p.candidate_id?'<div class="biz-note">已关联来源款式。罗盘展示价仅供研究，不会自动填成工厂报价；生产成本和收入请按实际填写。</div>':'')
      +'<div class="biz-panel"><div class="biz-form">'
      +select('mode','业务模式',[['供货 / 批发','供货 / 批发'],['自营零售','自营零售']],values.mode)
      +select('currency','币种',['CNY','USD','EUR','BRL','MXN','SGD','MYR'].map(x=>[x,x]),values.currency)
      +[['price','单件收入 / 报价'],['production','生产 / 拿货成本'],['target','目标利润率 %'],['quantity','测算数量 / 件']].map(([k,t])=>input(k,t,values[k],'number')).join('')
      +'<details class="wide"><summary>运费、包装、扣费与广告（按实际补充）</summary><div class="biz-form">'
      +[['packaging','包装辅料 / 件'],['inbound','交仓 / 头程 / 件'],['shipping','配送 / 履约 / 件'],['other','其他成本 / 件'],['loss','售后与扣费预留 / 件'],['commission','佣金 / 服务费率 %'],['tax','有效税费占收入 %'],['advertising','广告占收入 %']].map(([k,t])=>input(k,t,values[k],'number')).join('')+'</div></details>'
      +'</div><p class="hint">空白费用按 0 计算，请核对实际承担的费用；不预设平台费率。保存报告会同步人民币成本和报价到档案；其他币种独立测算。</p></div>'
      +'<div class="biz-section-actions">'+btn('calculate','计算利润',true)+btn('save-pricing','计算并保存报告')+btn('pricing-experiment','建立测款记录')+'</div><div id="biz-pricing-result">'+pricingOutput()+'</div>';
  }
  function pricingOutput() {
    if(!pricingResult)return '';
    const r=pricingResult.result,c=pricingResult.currency||'CNY';
    return `<div class="biz-kpis"><div class="biz-kpi ${r.unit_profit<0?'loss':''}"><small>单件预计利润 · ${esc(c)}</small><strong>${money(r.unit_profit)}</strong></div><div class="biz-kpi"><small>预计利润率</small><strong>${r.margin===null?'—':money(r.margin)+'%'}</strong></div><div class="biz-kpi"><small>盈亏平衡收入 · ${esc(c)}</small><strong>${money(r.break_even)}</strong></div></div>`+output(pricingResult.report);
  }
  function renderWorkflows() {
    const d=drafts['workflows:']||{};
    view().innerHTML=head('AI 工作流','先生成任务包，也可以使用自己配置的模型生成文字结果。')
      +'<div class="biz-panel"><div class="biz-form">'+select('module','选择任务',state.modules.map((name,i)=>[i,name]),d.module??2)
      +`<label>关联产品<select name="product_id">${productOptions(d.product_id??productId)}</select></label>`
      +select('platform','目标渠道',state.platforms.map(p=>[p,p]),d.platform||'供货 / 批发')+input('market','目标市场',d.market||'中国 / 供货')
      +textarea('brief','补充资料与任务要求',d.brief||candidateBrief)+'</div></div>'
      +'<div class="biz-tools">'+btn('compose','生成任务包',true)+btn('generate-ai','用已配置模型生成')+btn('copy-prompt','复制任务包')+'</div><p class="hint">点击模型生成会把当前产品和任务资料发给你配置的服务商，费用按服务商计费。图片和视频任务输出制作方案与脚本。</p>'
      +'<h2>任务包</h2>'+output(workflowPrompt)+`<div class="biz-panel">${textarea('result','文字结果 / 粘贴返回内容',d.result??workflowResult)}<div class="biz-tools">${btn('save-workflow','保存文字结果',true)}${btn('save-prompt','保存任务包')}${btn('export-workflow','导出当前文字')}</div></div>`;
  }
  function renderExperiments() {
    const d=drafts['experiments:'+experimentId]||state.experiments.find(x=>x.id===experimentId)||{};
    const real=state.experiments.filter(x=>!x.is_demo);
    const spent=real.reduce((a,x)=>a+Number(x.spent||0),0), revenue=real.reduce((a,x)=>a+Number(x.revenue||0),0);
    view().innerHTML=head('测款记录','记录真实投入和试卖结果，逐步验证新渠道。',btn('new-experiment','新建试验',true))
      +`<div class="biz-kpis"><div class="biz-kpi"><small>记录内实际支出</small><strong>¥ ${money(spent)}</strong></div><div class="biz-kpi"><small>记录内实际收入</small><strong>¥ ${money(revenue)}</strong></div><div class="biz-kpi"><small>现金收支差额</small><strong>¥ ${money(revenue-spent)}</strong></div></div><p class="hint">按人民币记录汇总，现金收支差额未计库存、应收和未支付成本，不等于会计净利润。</p>`
      +'<div class="biz-panel"><div class="biz-form"><label class="wide">关联产品<select name="product_id">'+productOptions(d.product_id??productId)+'</select></label>'+input('name','试验名称',d.name||activeProduct()?.name||'')+input('channel','渠道',d.channel||'')
      +input('date','记账日期',d.date||today(),'date')+select('status','进度',['计划中','进行中','已完成','暂停'].map(x=>[x,x]),d.status||'计划中')
      +[['budget','预算（元）'],['spent','实际支出（元）'],['revenue','实际收入（元）'],['hours','投入工时']].map(([k,t])=>input(k,t,d[k]||0,'number')).join('')
      +textarea('goal','验证目标',d.goal||'')+textarea('result','实际结果',d.result||'')+textarea('next','下一步',d.next||'')+'</div><div class="biz-tools">'+btn('save-experiment','保存试验',true)+'</div></div>'
      +`<div class="biz-table-wrap"><table class="biz-table"><tr><th>试验 / 渠道</th><th>日期</th><th>实际支出 / 收入</th><th>操作</th></tr>${state.experiments.map(x=>`<tr><td>${esc(x.name)} ${x.is_demo?'<span class="biz-tag demo">演示，不计汇总</span>':''}<div class="hint">${esc(x.channel)} · ${esc(x.status)}</div></td><td>${esc(x.date)}</td><td>¥ ${money(x.spent)} / ¥ ${money(x.revenue)}</td><td>${btn('edit-experiment','编辑',false,`data-id="${esc(x.id)}"`)}</td></tr>`).join('')}</table></div>`;
  }
  function renderArtifacts() {
    const selected=state.artifacts.find(x=>x.id===artifactId);
    view().innerHTML=head('成果资料','已保存的任务包、模型文字和计算报告。')
      +`<div class="biz-table-wrap"><table class="biz-table"><tr><th>名称</th><th>类型</th><th>操作</th></tr>${state.artifacts.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.kind)}</td><td>${btn('view-artifact','查看',false,`data-id="${esc(x.id)}"`)}</td></tr>`).join('')}</table>${state.artifacts.length?'':empty('还没有保存的成果。')}</div>`
      +(selected?'<div class="biz-panel"><h2>'+esc(selected.name)+'</h2>'+btn('copy-artifact','复制正文')+' '+btn('export-artifact','导出文档')+output(selected.content)+'</div>':'');
  }
  function renderSettings() {
    const s=state.settings;
    view().innerHTML=head('账号与设置','罗盘账号和模型服务分别配置，经营数据保存在本机。')
      +'<div class="biz-panel"><h2>罗盘数据</h2><p class="hint">沿用裤装桌面版的本机登录状态、收藏和采集缓存。登录失效时请在官网重新扫码。</p><div class="biz-tools">'+btn('open-compass','罗盘账号')+btn('collection-settings','榜单更新设置')+'</div></div>'
      +'<div class="biz-panel"><h2>AI 文字模型（可选）</h2><div class="biz-form">'+input('api_base','接口地址',s.api_base)+input('api_model','模型名称',s.api_model)
      +input('api_key',s.has_key?'新密钥（已保存密钥，留空继续使用）':'API 密钥','','password')+input('monthly_budget','每月试错预算（元）',s.monthly_budget,'number')
      +'<label class="check"><input name="clear_key" type="checkbox" style="width:auto">清除已保存的模型密钥</label></div><div class="biz-tools">'+btn('save-settings','保存设置',true)+'</div><p class="hint">密钥用当前 Windows 账户加密保存，不写入备份。</p></div>'
      +'<div class="biz-panel"><h2>经营资料备份与旧版迁移</h2><p class="hint">旧版 1.3 可先在“设置与备份”导出 JSON，再在这里合并恢复。不会删除原有文件，恢复前会自动保存当前资料备份。罗盘登录状态单独保留。</p><div class="biz-tools">'+btn('backup','导出经营备份')+btn('restore','合并恢复 / 导入旧版备份')+'</div></div>';
  }
  function renderAnalytics() {
    const d=drafts['analytics:']||{};
    view().innerHTML=head('数据分析','导入市场表格，或按同一统计周期计算广告指标。')
      +'<div class="biz-panel"><h2>市场指标</h2><p class="hint">CSV / TSV 表头包含价格、月销量；此处是精确值样本分析，不接收罗盘区间作为精确月销量。</p><div class="biz-tools">'+btn('market-report','选择市场表并分析',true)+'</div></div>'
      +'<div class="biz-panel"><h2>广告指标</h2><div class="biz-form">'+[['impressions','曝光量'],['clicks','点击量'],['orders','订单量'],['spend','广告花费'],['revenue','广告销售额'],['unit_profit','广告前单件贡献']].map(([k,t])=>input(k,t,d[k]||'','number')).join('')+'</div><div class="biz-tools">'+btn('ad-report','计算广告指标')+btn('save-analysis','保存报告')+'</div></div>'+output(report);
  }
  function renderIntake(advanced=false) {
    page='intake';
    const d=drafts['intake:']||{};
    view().innerHTML=head(advanced?'表格与条件初筛':'添加选品线索','款名、商品链接、含列名的表格都能直接整理保存。',btn('back-candidates','返回候选'))
      +'<div class="biz-panel"><div class="biz-form">'+textarea('text','每行一个款名 / 链接，或粘贴整张表格',d.text||'')
      +select('strategy','参考条件',[['','自动选择 / 先保存线索'],...Object.entries(state.strategies).map(([key,s])=>[key,s.name])],d.strategy||'')
      +'<div id="biz-thresholds" class="wide biz-form"></div><details class="wide"><summary>数据来源（可后补）</summary><div class="biz-form">'+input('platform','平台',d.platform||'')+input('market','市场 / 站点',d.market||'')+input('currency','币种',d.currency||'')+input('as_of','统计日期',d.as_of||'','date')+'</div></details></div><div class="biz-tools">'+btn('save-intake','整理并保存',true)+btn('import-file','直接读取 Excel / CSV')+'</div><p class="hint">手工链接只登记线索，不自动获取实时销量；来源和数值缺失时保持待补。</p></div>';
    renderThresholds();
  }
  function renderThresholds() {
    const strategy=view().querySelector('[name=strategy]')?.value;
    const rules=state.strategies[strategy]?.rules||[];
    document.getElementById('biz-thresholds').innerHTML=rules.map(([field,op,title,value])=>input('rule:'+field+op,title,value,'number')).join('');
  }
  function intakeArgs() {
    const d=form(),thresholds={}; Object.entries(d).filter(([k])=>k.startsWith('rule:')).forEach(([k,v])=>{thresholds[k.slice(5)]=v;delete d[k];});
    return {...d,thresholds};
  }
  async function saveProduct() {
    const product=await call('save_product',{product:{...form(),...(productId?{id:productId}:{})}});
    delete drafts['products:'+productId];productId=product.id;await refresh();return product;
  }
  function resetPriceForProduct() {
    const d=drafts['pricing:']||{}, p=activeProduct();
    d.price=d.currency&&d.currency!=='CNY'?'':p?.[d.mode==='自营零售'?'retail_price':'supply_price']||'';
    d.production=d.currency&&d.currency!=='CNY'?'':p?.cost||'';
    drafts['pricing:']=d;pricingResult=null;
  }
  async function collect(group, meta, cost=false) {
    const saved=await call('import_compass',{group,meta});
    if(cost) {
      const product=await call('create_product',{candidate_id:saved.candidate_id}); productId=product.id;
      resetPriceForProduct(); await navigate('pricing'); resetPriceForProduct();renderPricing();
    }
    return saved;
  }
  async function syncFavorites() {
    if(!globalThis.pantsDesktop || !currentReport || !currentReport.groups)return 0;
    let count=0;
    for(const group of currentReport.groups.filter(g=>favorites.has(g.product.id))) {await collect(group,currentReport.meta);count++;}
    return count;
  }
  async function copy(value) {
    if(!value)throw new Error('请先生成或选择一份正文。');
    try {await navigator.clipboard.writeText(value);message('正文已复制。');}
    catch {message('未能自动复制，请在正文中选择文字复制。',true);}
  }
  view().addEventListener('change',async event=>{
    try {
      if(['biz-product-picker','biz-pricing-product'].includes(event.target.id)) {
        captureDraft();productId=event.target.value;
        if(page==='pricing')resetPriceForProduct();render();
      } else if(event.target.name==='strategy')renderThresholds();
      else if(page==='pricing'&&['currency','mode'].includes(event.target.name)) {
        captureDraft();
        if(event.target.name==='currency') {
          for(const k of ['price','production','packaging','inbound','shipping','other','loss'])drafts['pricing:'][k]='';
          pricingResult=null;renderPricing();message('已切换币种，请按同一币种重新填写金额。');
        } else {resetPriceForProduct();renderPricing();}
      }
    }catch(error){message(error.message,true);}
  });
  view().addEventListener('input',event=>{
    if(event.target.id==='biz-search')for(const row of view().querySelectorAll('tr[data-search]'))row.hidden=!row.dataset.search.includes(event.target.value.toLowerCase());
    if(page==='pricing'&&event.target.name){pricingResult=null;document.getElementById('biz-pricing-result').innerHTML='';}
  });
  view().addEventListener('click',async event=>{
    const target=event.target.closest('[data-action]');if(!target)return;
    const action=target.dataset.action;target.disabled=true;
    try {
      message('');
      if(action==='new-product'){captureDraft();productId='';delete drafts['products:'];renderProducts();}
      else if(action==='save-product'){await saveProduct();renderProducts();message('档案已保存。');}
      else if(action==='product-cost'||action==='product-ai'){await saveProduct();resetPriceForProduct();await navigate(action==='product-cost'?'pricing':'workflows');}
      else if(action==='candidate-cost'){const p=await call('create_product',{candidate_id:target.dataset.id});productId=p.id;await refresh();resetPriceForProduct();await navigate('pricing');}
      else if(action==='candidate-ai'){const r=await call('candidate_brief',{id:target.dataset.id});candidateBrief=r.brief;delete drafts['workflows:'];drafts['workflows:']={module:0,brief:r.brief};await navigate('workflows');}
      else if(action==='candidate-detail'){
        selectedCandidate=target.dataset.id;const r=await call('candidate_brief',{id:selectedCandidate});
        document.getElementById('biz-detail').innerHTML='<div class="biz-panel"><h2>来源与复核依据</h2>'+output(r.brief)+'<div class="biz-tools">'+['待复核','已验证','放弃'].map(s=>btn('review-'+s,'标记'+s)).join('')+'</div></div>';
      } else if(action.startsWith('review-')){await call('review_candidate',{id:selectedCandidate,status:action.slice(7)});await refresh();renderCandidates();message('复核状态已保存。');}
      else if(action==='intake'||action==='open-screen'){captureDraft();renderIntake(action==='open-screen');}
      else if(action==='back-candidates'){await navigate('candidates');}
      else if(action==='save-intake'||action==='import-file'){
        const r=await call(action==='save-intake'?'intake':'import_file',intakeArgs());if(r.cancelled)return;
        delete drafts['intake:'];page='candidates';await refresh();renderCandidates();message('已整理保存 '+r.ids.length+' 款。');
      } else if(action==='sync-favorites'){const count=await syncFavorites();await refresh();renderCandidates();message('已同步当前筛选范围内的 '+count+' 款收藏。');}
      else if(action==='calculate'||action==='save-pricing'){
        const values=form(),sourceProduct=productId;captureDraft();
        const r=await call('pricing',{values,product_id:sourceProduct,save:action==='save-pricing'});
        if(page==='pricing'&&productId===sourceProduct&&JSON.stringify(form())===JSON.stringify(values)){
          pricingResult={...r,currency:values.currency};document.getElementById('biz-pricing-result').innerHTML=pricingOutput();message(action==='save-pricing'?'计算完成，报告已保存。':'已按当前输入计算。');
        }else if(page==='pricing')message('输入已修改，请按当前资料重新计算。');
      } else if(action==='pricing-experiment'){captureDraft();experimentId='';delete drafts['experiments:'];await navigate('experiments');}
      else if(action==='compose'||action==='generate-ai'){
        const args=form();args.module=Number(args.module);captureDraft();
        if(action==='generate-ai')message('模型正在生成，可以切换页面，完成后结果会保存到成果资料。');
        const r=await call(action==='compose'?'compose':'generate_ai',args);workflowPrompt=r.prompt;if(r.content)workflowResult=r.content;
        if(page==='workflows'){if(r.content&&drafts['workflows:'])drafts['workflows:'].result=r.content;renderWorkflows();message(r.content?'生成成功，结果已保存。':'任务包已生成。');}
      } else if(action==='copy-prompt')await copy(workflowPrompt);
      else if(action==='save-workflow'||action==='save-prompt'){
        workflowResult=form().result||'';await call('save_artifact',{name:state.modules[Number(form().module)],product_id:form().product_id,kind:action==='save-prompt'?'AI任务包':'文字成果',content:action==='save-prompt'?workflowPrompt:workflowResult});message('已保存到成果资料。');
      } else if(action==='export-workflow')await call('export_report',{content:form().result||workflowPrompt});
      else if(action==='new-experiment'){captureDraft();experimentId='';delete drafts['experiments:'];renderExperiments();}
      else if(action==='edit-experiment'){captureDraft();experimentId=target.dataset.id;renderExperiments();}
      else if(action==='save-experiment'){const r=await call('save_experiment',{experiment:{...form(),...(experimentId?{id:experimentId}:{})}});delete drafts['experiments:'+experimentId];experimentId=r.id;await refresh();renderExperiments();message('测款记录已保存。');}
      else if(action==='view-artifact'){artifactId=target.dataset.id;renderArtifacts();}
      else if(action==='copy-artifact')await copy(state.artifacts.find(x=>x.id===artifactId)?.content);
      else if(action==='export-artifact')await call('export_report',{content:state.artifacts.find(x=>x.id===artifactId)?.content||''});
      else if(action==='save-settings'){const r=await call('save_settings',form());state.settings=r;renderSettings();message('设置已保存。');}
      else if(action==='open-compass')host.postMessage({action:'open-compass'});
      else if(action==='collection-settings')host.postMessage({action:'collection-settings'});
      else if(action==='backup'||action==='restore'){const r=await call(action);if(!r.cancelled){await refresh();message(r.message);}}
      else if(action==='market-report'||action==='ad-report'){const r=await call(action==='market-report'?'market_report':'ad_report',action==='ad-report'?{values:form()}:{currency:'CNY'});if(!r.cancelled){report=r.report;captureDraft();renderAnalytics();}}
      else if(action==='save-analysis'){await call('save_artifact',{name:'数据分析报告',kind:'分析报告',content:report});message('报告已保存。');}
    }catch(error){message(error.message,true);}
    finally {if(target.isConnected)target.disabled=false;}
  });
  document.getElementById('cards').addEventListener('click',async event=>{
    const costButton=event.target.closest('[data-business-product]');
    const favoriteButton=event.target.closest('[data-favorite]');
    const id=costButton?.dataset.businessProduct||favoriteButton?.dataset.favorite;
    if(!id||!currentReport)return;
    if(favoriteButton&&!favorites.has(id))return;
    const group=currentReport.groups.find(g=>g.product.id===id);if(!group)return;
    try {if(costButton)costButton.disabled=true;await collect(group,currentReport.meta,Boolean(costButton));}
    catch(error){notice(error.message,true);}
    finally{if(costButton?.isConnected)costButton.disabled=false;}
  });
  const oldRenderCard=renderCard;
  renderCard=group=>oldRenderCard(group).replace('<div class="product-actions">','<div class="product-actions">'+(host?`<button class="primary" type="button" data-business-product="${esc(group.product.id)}">建档算利润</button>`:''));
  async function runSmoke() {
    try {
      await refresh();
      if(!currentReport?.groups?.length)throw new Error('演示榜单未加载');
      const group=currentReport.groups[0];
      const waitFor=async test=>{for(let i=0;i<300;i++){if(test())return;await new Promise(resolve=>setTimeout(resolve,100));}throw new Error('界面动作超时：'+page);};
      document.querySelector('[data-business-product]').click();
      await waitFor(()=>page==='pricing'&&view().querySelector('[data-action=save-pricing]'));
      const imported=await collect(group,currentReport.meta);
      const p=await call('create_product',{candidate_id:imported.candidate_id});
      if(p.cost||p.supply_price||p.retail_price)throw new Error('来源价格被错误带入工厂报价');
      view().querySelector('[name=price]').value='30';view().querySelector('[name=production]').value='20';
      view().querySelector('[data-action=save-pricing]').click();
      await waitFor(()=>pricingResult!==null);
      const r=pricingResult;await refresh();const updated=state.products.find(x=>x.id===p.id);
      if(updated.cost!=='20'||updated.supply_price!=='30')throw new Error('报价未同步到产品档案');
      if(r.result.unit_profit!==10)throw new Error('利润衔接失败');
      const task=await call('compose',{module:2,product_id:updated.id,platform:'供货 / 批发',market:'中国',brief:'测试文案'});
      if(!task.prompt.includes(group.product.name))throw new Error('档案未进入任务包');
      await call('save_experiment',{experiment:{name:updated.name,product_id:updated.id,channel:'测试供货',date:today(),status:'计划中',budget:100,spent:0,revenue:0,hours:0,goal:'测试',result:'',next:'核对成本'}});
      await refresh();
      if(state.candidates.length!==1||state.products.length!==1||state.experiments.length!==1)throw new Error('重复入库或经营记录失败');
      for(const route of ['candidates','products','pricing','workflows','experiments','artifacts','settings','analytics'])await navigate(route);
      await navigate('candidates');
      window.unifiedSmokeResult={passed:true,candidates:state.candidates.length,products:state.products.length,experiments:state.experiments.length,unit_profit:r.result.unit_profit,rangeNotUsedAsPrice:true,workflowHasSource:task.prompt.includes('来源平台'),actualCardAndPricingButtons:true,bodyText:document.body.innerText.slice(-2500)};
    }catch(error){window.unifiedSmokeResult={passed:false,error:error.message};}
  }
  globalThis.businessUI={receive,navigate,showPants,collect,syncFavorites,runSmoke};
})();
