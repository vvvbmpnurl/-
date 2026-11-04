/* Connected production workflow, separate from the existing copywriting scanner. */
(() => {
  'use strict';
  const box = document.createElement('div');
  box.className = 'card cf-workspace';
  box.id = 'cfWorkspace';
  const bar = document.querySelector('#p4 .topbar');
  bar.after(box);
  let state = null;
  let busy = false;
  const labels = {awaiting_upload:'等待外部工具制作 / 回传',creating:'正在提交',processing:'平台制作中',ready:'成片待审核',failed:'失败',unknown:'结果待核实',queued:'排队中',sending:'正在分发',submitted:'平台已受理',published:'已发布'};
  const e = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeURL = value => { try { const u = new URL(value); return u.protocol === 'https:' ? e(u.href) : ''; } catch { return ''; } };
  async function api(path, data) {
    const res = await fetch('/api/factory/' + path, data === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json','X-Factory-CSRF':state.csrf}, body:JSON.stringify(data)
    });
    const json = await res.json();
    if (!res.ok) throw Error(json.error || '请求失败');
    return json;
  }
  function sources() { return typeof OUTPUTS === 'undefined' ? [] : OUTPUTS; }
  function fillSources() {
    const sel = document.getElementById('cfSource');
    if (!sel) return;
    const old = sel.value;
    sel.innerHTML = '<option value="">选择已生成的选题成稿，或直接填写</option>' + sources().map(o => `<option value="${e(o.id)}">${e(o.platName)} · ${e(o.title)}</option>`).join('');
    if (sources().some(o => o.id === old)) sel.value = old;
  }
  function render() {
    box.innerHTML = `<div class="card-h"><h3>视频制作与多账号分发 <small>接入平台 · 成片审核 · 发布追踪</small></h3><button class="btn ghost sm" data-action="reload">刷新任务</button></div>
    <div class="cf-steps"><span>01 选题成稿</span><span>02 AI / 数字人制作</span><span>03 人工审核成片</span><span>04 多账号分发</span></div>
    <div class="note ${state.publish_ready ? '' : 'warn'}">制作平台：${state.providers.map(p => `${e(p.name)} <b>${p.mode==='manual'?'手动制作':p.ready ? '已配置' : '未配置'}</b>`).join('；')}。发布服务：<b>${state.publish_ready ? '已配置，需有效账号授权' : '未接入'}</b>。配置状态不代表平台连通性已验证。</div>
    <details class="cf-tool-guide"><summary>查看本次指定的制作与分发工具（12 款）</summary><div class="tbl-wrap"><table><thead><tr><th>工具</th><th>用途</th><th>当前接入方式</th><th>入口</th></tr></thead><tbody>${(state.tools||[]).map(t=>`<tr><td>${e(t.name)}</td><td>${e(t.category)}</td><td>${e(t.note)}</td><td><a href="${safeURL(t.url)}" target="_blank" rel="noopener noreferrer">打开工具 ↗</a>${t.docs?` · <a href="${safeURL(t.docs)}" target="_blank" rel="noopener noreferrer">官方说明</a>`:''}</td></tr>`).join('')}</tbody></table></div><p class="prov">价格、免费额度、可用模型与账号权限以平台当前控制台为准。手动制作和待适配不代表已直连。</p></details>
    <div class="cf-compose"><div><label>选用现有成稿</label><select id="cfSource"></select><label>视频标题</label><input id="cfTitle" maxlength="200" placeholder="也可以直接填写一个新选题"><label>制作平台</label><select id="cfProvider">${state.providers.map(p=>`<option value="${e(p.id)}" ${p.ready?'':'disabled'}>${e(p.name)}${p.mode==='manual'?' · 制作包/回传':p.ready?' · API已配置':' · API未配置'}</option>`).join('')}</select><p class="prov">闪剪：数字人口播（无包装，字幕/剪辑需后续处理）；万相：5 秒无口播空镜。其余工具当前使用制作包回传，不会自动在网页提交。</p></div>
    <div><label>制作稿 / 视频画面提示词</label><textarea id="cfScript" rows="7" maxlength="5000" placeholder="数字人填写口播全文；AI 空镜填写一个镜头的画面描述。提交后保留此版本，修改稿件请新建制作任务。"></textarea><button class="btn" data-action="create" ${state.providers.some(p=>p.ready)?'':'disabled'}>创建制作任务</button><span class="prov"> 制作成功后在下方预览与审核</span></div></div>
    <div id="cfFeedback" role="status" aria-live="polite"></div><div id="cfJobs"></div><h4 class="cf-record-title">多账号分发记录</h4><div id="cfDeliveries"></div>`;
    fillSources();
    renderJobs();
  }
  function renderJobs() {
    document.getElementById('cfJobs').innerHTML = state.jobs.length ? state.jobs.map(j => {
      const reviewed = j.review?.decision === 'approved';
      const url = safeURL(j.video_url);
      const sent = state.deliveries.some(d=>d.job===j.id);
      return `<article class="cf-job" data-job="${e(j.id)}"><div class="card-h"><h4>${e(j.title)}</h4><span class="tagx ${reviewed?'tx-ok':'tx-cool'}">${reviewed?'人工审核通过':j.review?.decision==='rejected'?'已退回修改':e(labels[j.status] || j.status)}</span></div>
      <p class="prov">${e((state.tools||[]).find(t=>t.id===j.provider)?.name||j.provider)} · ${e(new Date(j.created*1000).toLocaleString('zh-CN'))}${j.remote_id?` · 平台任务：${e(j.remote_id)}`:''}</p>
      <details><summary>查看本次制作稿</summary><pre class="cf-script">${e(j.script)}</pre></details>
      ${j.error?`<div class="note warn">${e(j.error)}</div>`:''}
      ${url?`<video controls preload="none" src="${url}" class="cf-video"></video><p><a href="${url}" target="_blank" rel="noopener noreferrer">打开成片 / 在平台链接中下载 ↗</a> <span class="prov">平台视频地址可能过期，请及时下载保存</span></p>`:''}
      ${j.status==='awaiting_upload'?`<div class="cf-handoff"><p>① 下载制作包和字幕 → ② 在所选工具中完成制作 → ③ 回传可直接播放的 HTTPS 成片链接</p><button class="btn ghost sm" data-action="package">下载制作包 .json</button> <button class="btn ghost sm" data-action="script">口播稿 .txt</button> <button class="btn ghost sm" data-action="subtitle" ${j.srt?'':'disabled'}>字幕 .srt</button> <a class="btn ghost sm" href="${safeURL((state.tools||[]).find(t=>t.id===j.provider)?.url)}" target="_blank" rel="noopener noreferrer">打开制作工具 ↗</a><label>HTTPS 成片直链（不是网盘分享页；须能供浏览器播放和发布服务读取）<input class="cf-import-url" type="url" placeholder="https://.../video.mp4"></label><button class="btn sm" data-action="import">回传成片，进入人工审核</button><p class="prov">系统只保存链接，不会自动验证成片与口播一致；请人工完整观看。当前暂不支持本地文件上传，更换成片必须新建版本。</p></div>`:''}
      ${j.status==='processing'?'<button class="btn ghost sm" data-action="refresh">查询制作进度</button>':''}
      ${j.status==='ready'&&!sent?`<div class="cf-review"><label><input type="checkbox" class="cf-watched"> 我已完整观看成片，检查画面、字幕、音频、素材授权与 AI 标识</label><textarea class="cf-note" rows="2" maxlength="2000" placeholder="审核意见（退回必填）">${e(j.review?.note||'')}</textarea><button class="btn sm" data-action="approve">审核通过</button> <button class="btn ghost sm" data-action="reject">退回修改</button><p class="prov">文案扫描不替代成片人工审核；退回后请修改制作稿并新建任务。</p></div>`:''}
      ${reviewed?`<div class="cf-accounts"><button class="btn ghost sm" data-action="distribution-pack">导出分发清单 .json</button><p class="prov">可用于蚁小二 / 易媒助手人工提交；清单导出不会执行发布，不保证服务可自动导入此格式。</p><b>选择分发账号</b><div>${state.accounts.length?state.accounts.map(a=>`<label><input type="checkbox" value="${e(a.id)}" class="cf-account"> ${e(a.name)} · ${e({dy:'抖音',xhs:'小红书',sph:'视频号'}[a.platform]||a.platform)}</label>`).join(''):'<p class="prov">暂无配置的授权账号，请先在发布服务授权，再配置服务端账号清单。</p>'}</div><button class="btn sm" data-action="publish" ${state.publish_ready&&state.accounts.length?'':'disabled'}>一键分发所选账号</button><p class="prov">立即向所选账号提交；同一任务同一账号不重复提交。最终发布状态以平台回执为准。</p></div>`:''}</article>`;
    }).join('') : '<div class="hint">还没有视频任务。选题成稿完成后，选择制作平台提交第一条视频。</div>';
    document.getElementById('cfDeliveries').innerHTML = state.deliveries.length ? `<div class="tbl-wrap"><table><thead><tr><th>视频</th><th>账号</th><th>结果</th><th>详情</th></tr></thead><tbody>${state.deliveries.map(d=>`<tr><td>${e(state.jobs.find(j=>j.id===d.job)?.title||d.job)}</td><td>${e(d.account_name)}</td><td>${e(labels[d.status]||d.status)}</td><td>${d.error?e(d.error):''} ${safeURL(d.url)?`<a href="${safeURL(d.url)}" target="_blank" rel="noopener noreferrer">查看作品 ↗</a>`:''} ${d.remote_id&&['submitted','unknown'].includes(d.status)?`<button class="mini-btn" data-delivery="${e(d.id)}" data-action="delivery">查询发布结果</button>`:''}</td></tr>`).join('')}</tbody></table></div>` : '<p class="prov">审核通过并选择账号后，分发结果将在这里逐个显示。</p>';
  }
  function download(name, content) {
    const url=URL.createObjectURL(new Blob([content||''],{type:'text/plain;charset=utf-8'}));
    const a=document.createElement('a'); a.href=url; a.download=name; a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function reload() {
    state = await api('state');
    if (document.getElementById('cfJobs')) { renderJobs(); fillSources(); }
    else render();
  }
  box.addEventListener('change', event=>{
    if(event.target.id==='cfProvider') {
      const p=state.providers.find(p=>p.id===event.target.value);
      document.querySelector('[data-action="create"]').textContent=p?.mode==='manual'?'创建手动制作任务':'提交 API 制作';
    }
    if(event.target.id !== 'cfSource') return;
    const o=sources().find(o=>o.id===event.target.value);
    if(!o) return;
    document.getElementById('cfTitle').value=o.title;
    document.getElementById('cfScript').value=typeof buildPack==='function'?buildPack(o).voFull:o.body;
  });
  box.addEventListener('click', async event => {
    const button=event.target.closest('[data-action]');
    if(!button || button.disabled || busy) return;
    if(['package','script','subtitle','distribution-pack'].includes(button.dataset.action)) {
      const j=state.jobs.find(j=>j.id===button.closest('[data-job]').dataset.job);
      const action=button.dataset.action;
      if(action==='distribution-pack') {
        if(j.review?.decision!=='approved') return;
        const ids=[...button.closest('[data-job]').querySelectorAll('.cf-account:checked')].map(x=>x.value);
        download(j.id+'-分发清单.json',JSON.stringify({task_id:j.id,title:j.title,description:j.script,video_url:j.video_url,ai_generated:true,review:j.review,accounts:state.accounts.filter(a=>ids.includes(a.id)),instructions:'仅为人工分发清单，不会执行发布；平台账号授权和最终发布请在蚁小二或易媒助手完成。'},null,2));
        return;
      }
      const content=action==='script'?j.script:action==='subtitle'?j.srt:JSON.stringify({task_id:j.id,tool:j.provider,title:j.title,script:j.script,srt:j.srt,aspect_ratio:'9:16',ai_generated:true,instructions:'在目标工具中制作并保留AI标识；完成后回传HTTPS成片直链，人工审核。制作包不会自动上传或导入工程。'},null,2);
      download(j.id+(action==='package'?'.json':action==='subtitle'?'.srt':'.txt'), content);
      return;
    }
    const action=button.dataset.action;
    const article=button.closest('[data-job]');
    const ident=article?.dataset.job;
    busy=true; button.disabled=true;
    const feedback=document.getElementById('cfFeedback');
    feedback.textContent='正在处理，请勿重复提交…';
    try {
      if(action==='reload') await reload();
      if(action==='create') {
        const provider=document.getElementById('cfProvider').value;
        const title=document.getElementById('cfTitle').value.trim();
        const script=document.getElementById('cfScript').value.trim();
        if(!title||!script) throw Error('请填写标题和制作稿');
        const source=document.getElementById('cfSource').value;
        const o=sources().find(o=>o.id===source);
        const original=o&&typeof buildPack==='function'?buildPack(o):null;
        const srt=original&&script===original.voFull?original.srt:'';
        await api('jobs',{provider,title,script,source,srt});
      }
      if(action==='import') await api(`jobs/${ident}/import`,{video_url:article.querySelector('.cf-import-url').value});
      if(action==='refresh') await api(`jobs/${ident}/refresh`,{});
      if(['approve','reject'].includes(action)) await api(`jobs/${ident}/review`,{decision:action==='approve'?'approved':'rejected',note:article.querySelector('.cf-note').value,watched:article.querySelector('.cf-watched').checked});
      if(action==='publish') {
        const accounts=[...article.querySelectorAll('.cf-account:checked')].map(x=>x.value);
        if(!accounts.length) throw Error('请至少选择一个分发账号');
        await api(`jobs/${ident}/publish`,{accounts});
      }
      if(action==='delivery') await api(`deliveries/${button.dataset.delivery}/refresh`,{});
      await reload();
      feedback.textContent=action==='publish'?'分发请求已处理，请查看每个账号的结果。':'操作已完成，任务状态已更新。';
    } catch(err) {
      feedback.textContent=err.message || '请求失败，请刷新状态核实结果';
      // Reconcile persisted tasks after network failures without resubmitting.
      if(action!=='reload') { try { await reload(); } catch {} }
    } finally { busy=false; if(button.isConnected) button.disabled=false; }
  });
  const observer=new MutationObserver(fillSources);
  const outputs=document.getElementById('outList')||document.getElementById('outCount');
  if(outputs) observer.observe(outputs,{childList:true,subtree:true});
  reload().catch(()=>{
    box.innerHTML='<div class="card-h"><h3>视频制作与多账号分发</h3></div><div class="note warn">当前页面未连接内容工厂服务。请在项目目录运行 <code>python3 server.py</code>，通过 <a href="http://127.0.0.1:8765">http://127.0.0.1:8765</a> 打开工作台。视频 API 密钥和发布账号在服务端配置，静态页面不能直接调用。</div>';
  });
})();
