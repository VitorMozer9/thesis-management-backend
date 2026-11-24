/* UFVJM TCCs — camada compartilhada do frontend. Sem bibliotecas externas. */
(function () {
  'use strict';
  const STORAGE = {
    mode: 'ufvjm-tcc-mode-v1', api: 'ufvjm-tcc-api-v1',
    demo: 'ufvjm-tcc-demo-v1', real: 'ufvjm-tcc-real-v1'
  };
  const SAMPLE_RECORDS = [
    { id:'11111111-1111-4111-8111-111111111111', title:'Exemplo TCC de Sistemas 1', abstract:'Resumo breve de explicação do TCC, contendo seus objetivos, método e principais resultados. Um exemplo para demonstrar o repositório.', student_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', course_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', author:'Ana Beatriz e Pedro Henrique', course:'Sistemas de Informação', advisor:'Prof. Ricardo Souza', keywords:['arquitetura','sistemas de informação'], year:'2026', status:'published', cover:1, file_name:'exemplo-tcc-1.pdf', reviewDate:'2026-10-21', feedback:'' },
    { id:'22222222-2222-4222-8222-222222222222', title:'Exemplo TCC de Sistemas 2', abstract:'Resumo breve de explicação do TCC, contendo seu tema, introdução e objetivos. Trabalho utilizado como exemplo do fluxo de avaliação.', student_id:'cccccccc-cccc-4ccc-8ccc-cccccccccccc', course_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', author:'Mariana Costa', course:'Sistemas de Informação', advisor:'Profa. Juliana Martins', keywords:['engenharia de software','gestão de projetos'], year:'2026', status:'submitted', cover:2, file_name:'exemplo-tcc-2.pdf', reviewDate:'', feedback:'' },
    { id:'33333333-3333-4333-8333-333333333333', title:'Exemplo TCC de Sistemas 3', abstract:'Resumo breve de explicação do TCC, contendo a proposta, os dados principais e uma síntese da contribuição acadêmica.', student_id:'dddddddd-dddd-4ddd-8ddd-dddddddddddd', course_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', author:'Lucas Almeida', course:'Sistemas de Informação', advisor:'Prof. Marcelo Oliveira', keywords:['redes','segurança'], year:'2026', status:'advisor_rejected', cover:3, file_name:'exemplo-tcc-3.pdf', reviewDate:'', feedback:'' }
  ];
  const el = (selector, root=document) => root.querySelector(selector);
  const els = (selector, root=document) => Array.from(root.querySelectorAll(selector));
  function mode() { return localStorage.getItem(STORAGE.mode) === 'api' ? 'api' : 'demo'; }
  function apiBase() { return (localStorage.getItem(STORAGE.api) || 'http://127.0.0.1:8000/api').replace(/\/+$/, ''); }
  function readJson(key, fallback) {
    try { const parsed=JSON.parse(localStorage.getItem(key)); return parsed ?? fallback; }
    catch { return fallback; }
  }
  function seedDemo() {
    if (!localStorage.getItem(STORAGE.demo)) localStorage.setItem(STORAGE.demo, JSON.stringify(SAMPLE_RECORDS));
  }
  function records(which=mode()) { if (which==='demo') seedDemo(); return readJson(which==='demo'?STORAGE.demo:STORAGE.real, []); }
  function saveRecords(items,which=mode()) { localStorage.setItem(which==='demo'?STORAGE.demo:STORAGE.real, JSON.stringify(items)); }
  function upsert(record,which=mode()) {
    const current=records(which); const index=current.findIndex(item=>item.id===record.id);
    if(index>=0) current[index]={...current[index],...record}; else current.unshift(record);
    saveRecords(current,which); return current[index>=0?index:0];
  }
  function getLocal(id,which=mode()) { return records(which).find(item=>item.id===id)||null; }
  function uuid() {
    if (typeof crypto!=='undefined' && typeof crypto.randomUUID==='function') return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{let r=Math.random()*16|0;return(c==='x'?r:(r&3|8)).toString(16)});
  }
  function validUuid(value) { return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value).trim()); }
  function escapeHtml(value) {return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function keywords(value) {return String(value||'').split(',').map(x=>x.trim()).filter(Boolean);}
  function statusView(record) {
    const status=record.status||'draft';
    if(record.reviewDecision==='pending') return {label:'Com pendências',type:'review',icon:'hourglass'};
    const m={
      draft:['Rascunho','draft','edit'],
      submitted:['Em análise','review','hourglass'],
      advisor_approved:['Aprovado','done','check'],
      advisor_rejected:['Pendente','pending','ban'],
      defense_approved:['Concluído','done','check'],
      defense_rejected:['Reprovado','pending','ban'],
      published:['Concluído','done','check']
    };
    const [label,type,icon]=m[status]||[String(status),'draft','edit'];
    return {label,type,icon};
  }
  function statusIcon(icon) {
    if(icon==='check') return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 12 6 6L21 5"/></svg>';
    if(icon==='ban') return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M5.6 18.4 18.4 5.6"/></svg>';
    if(icon==='hourglass') return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12M6 21h12M8 3c0 6 8 7 8 9s-8 3-8 9m8-18c0 6-8 7-8 9s8 3 8 9"/></svg>';
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 17 12-12 3 3L7 20H4Z"/></svg>';
  }
  function showNotice(target,text,type='info') {
    if(!target)return;
    target.textContent=text;target.className='notice notice-'+type;target.hidden=false;
  }
  function toast(message,error=false) {
    let root=el('#toast-root');if(!root){root=document.createElement('div');root.id='toast-root';document.body.appendChild(root)}
    const div=document.createElement('div');div.className='toast'+(error?' error':'');div.textContent=message;div.setAttribute('role','status');root.appendChild(div);
    setTimeout(()=>div.remove(),5600);
  }
  function describeError(e) {
    if (e instanceof TypeError) return 'Não foi possível conectar à API. Confira o endereço, se o servidor está ativo e as permissões CORS.';
    return e?.message || 'Erro inesperado ao acessar a API.';
  }
  async function apiRequest(path,options={}) {
    const url=apiBase()+path;
    const headers={Accept:'application/json',...(options.headers||{})};
    const init={method:options.method||'GET',headers};
    if(options.body instanceof FormData) init.body=options.body;
    else if(options.body!==undefined){headers['Content-Type']='application/json';init.body=JSON.stringify(options.body)}
    const response=await fetch(url,init);
    const contentType=response.headers.get('content-type')||'';
    const body=contentType.includes('json')?await response.json():await response.text();
    if(!response.ok){
      const details=typeof body==='string'?body.slice(0,150):JSON.stringify(body);
      const error=new Error(`Erro ${response.status} na API: ${details}`); error.status=response.status;throw error;
    }
    return body;
  }
  async function fetchThesis(id) {
    if (!validUuid(id)) throw new Error('Informe um UUID válido.');
    const result=await apiRequest(`/theses/${id}/`);
    return upsert({...getLocal(id,'api'),...result},'api');
  }
  function syncModePills() {
    els('[data-mode-label]').forEach(e=>{e.textContent=mode()==='api'?'API real':'Demonstração';e.classList.toggle('is-api',mode()==='api')});
  }
  function settingsDialog() {
    const dialog=document.createElement('dialog');dialog.id='settings-dialog';dialog.className='settings-dialog';
    dialog.innerHTML=`<div class="settings-header"><div><h2>Configurações</h2><p>Selecione o ambiente e o endereço do backend.</p></div><button type="button" class="modal-close" id="settings-close" aria-label="Fechar">×</button></div>
      <form id="settings-form">
        <div class="setting-block"><label class="title-label">Modo de funcionamento</label>
          <label class="radio-option"><input type="radio" name="app-mode" value="demo"><span><strong>Demonstração</strong><small>Trabalhos fictícios e interações locais. Nenhuma chamada de API.</small></span></label>
          <label class="radio-option"><input type="radio" name="app-mode" value="api"><span><strong>API real</strong><small>Criar, consultar, editar rascunhos e enviar PDFs ao backend Django. As demais ações ficam indisponíveis.</small></span></label>
        </div>
        <div class="setting-block"><label for="settings-api-url" class="title-label">URL-base da API</label><input class="settings-input" id="settings-api-url" type="text" placeholder="http://127.0.0.1:8000/api"><p style="font-size:12px;color:#69737b;margin:6px 0 0">Exemplo: http://127.0.0.1:8000/api · A API atual usa o prefixo /api.</p></div>
        <div class="settings-foot"><button class="btn btn-primary" type="submit">Salvar configurações</button></div>
      </form>`;
    document.body.appendChild(dialog);
    el('#settings-close',dialog).addEventListener('click',()=>dialog.close());
    dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
    el('#settings-form',dialog).addEventListener('submit',e=>{
      e.preventDefault();const selected=el('input[name="app-mode"]:checked',dialog)?.value||'demo';
      const entered=el('#settings-api-url',dialog).value.trim().replace(/\/+$/,'');
      if(!entered || !(entered.startsWith('/api')||/^https?:\/\//i.test(entered))){toast('Use uma URL HTTP(S) ou um caminho como /api.',true);return}
      localStorage.setItem(STORAGE.mode,selected);localStorage.setItem(STORAGE.api,entered);
      dialog.close();location.reload();
    });
    return dialog;
  }
  function initialize() {
    seedDemo();syncModePills();let dialog;
    els('[data-open-settings]').forEach(button=>button.addEventListener('click',()=>{
      if(!dialog)dialog=settingsDialog();
      el(`input[name="app-mode"][value="${mode()}"]`,dialog).checked=true;
      el('#settings-api-url',dialog).value=apiBase();dialog.showModal();
    }));
  }
  document.addEventListener('DOMContentLoaded',initialize);
  window.TccApp={mode,apiBase,records,upsert,getLocal,uuid,validUuid,escapeHtml,keywords,statusView,statusIcon,showNotice,toast,describeError,apiRequest,fetchThesis,el,els};
})();
