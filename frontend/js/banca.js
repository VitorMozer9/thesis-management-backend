document.addEventListener('DOMContentLoaded',async()=>{
  const app=window.TccApp;
  const real=app.mode()==='api';
  const lookup=app.el('#review-lookup');
  const idInput=app.el('#review-id');
  let record=null;
  const note=app.el('#review-mode-note');
  app.showNotice(note,real
    ?'A API permite consultar os dados e o status do TCC por UUID, mas ainda não oferece endpoints para avaliação, marcação de banca ou download do PDF. Os controles de decisão estão desabilitados.'
    :'Demonstração: as decisões abaixo alteram somente os dados armazenados neste navegador. Nenhuma avaliação é enviada ao backend.', 'info');

  function setReviewDisabled(state){
    ['#reject-button','#pending-button','#approve-button','#review-feedback','#defense-date','#no-date'].forEach(s=>app.el(s).disabled=state);
  }
  function render(){
    const exists=Boolean(record);
    app.el('#review-main').hidden=!exists;
    app.el('#review-empty').hidden=exists;
    if(!exists)return;
    const status=app.statusView(record);
    app.el('#review-student').textContent=real?`Aluno: ${record.student_id||'não informado'} · Curso: ${record.course_id||'não informado'}`:`${record.author||'Aluno'} — ${record.course||'Curso não informado'}`;
    app.el('#review-advisor').textContent=`Orientador: ${record.advisor||'não informado'}`;
    app.el('#review-title').textContent=record.title||'Título não informado';
    app.el('#review-status').textContent='Situação: '+status.label;
    app.el('#review-pdf-title').textContent=record.file_name|| (record.file_key?'PDF associado ao TCC':'Nenhum PDF anexado');
    app.el('#review-pdf-detail').textContent=record.file_key?`Arquivo armazenado: ${record.file_key}`:record.file_name?'Arquivo ilustrativo da demonstração, sem conteúdo para baixar.':'Nenhum arquivo foi enviado para este trabalho.';
    app.el('#review-file-info').textContent=record.file_sha256?'Hash SHA-256: '+record.file_sha256.slice(0,16)+'…':record.file_name?'Arquivo de demonstração':'Sem arquivo';
    const download=app.el('#download-button');download.disabled=true;
    download.title='O backend atual não possui rota de download. Na demonstração não há PDF real anexado.';
    app.el('#review-feedback').value=record.feedback||'';
    app.el('#defense-date').value=record.reviewDate||'';
    app.el('#no-date').checked=Boolean(record.noDate);
    setReviewDisabled(real);
    app.el('#defense-date').disabled=real||Boolean(record.noDate);
    app.el('#review-footnote').textContent=real?'Avaliações, ressalvas e datas exibidas no protótipo não podem ser persistidas na API atual.':'As alterações de avaliação, ressalvas e data são apenas locais. O botão Baixar requer um futuro endpoint da API.';
  }
  async function open(id){
    if(!app.validUuid(id)){app.toast('Informe um UUID válido.',true);return}
    try{
      record=real?await app.fetchThesis(id):app.getLocal(id,'demo');
      if(!record)throw new Error('Trabalho não encontrado na demonstração.');
      idInput.value=record.id;
      history.replaceState(null,'','banca.html?id='+encodeURIComponent(record.id));
      render();
    }catch(error){record=null;render();app.toast(app.describeError(error),true)}
  }
  lookup.addEventListener('submit',event=>{event.preventDefault();open(idInput.value.trim())});
  app.el('#no-date').addEventListener('change',event=>{
    if(!record||real)return;
    app.el('#defense-date').disabled=event.target.checked;
    if(event.target.checked)app.el('#defense-date').value='';
    record=app.upsert({...record,noDate:event.target.checked,reviewDate:app.el('#defense-date').value},'demo');
  });
  app.el('#review-feedback').addEventListener('change',event=>{
    if(record&&!real)record=app.upsert({...record,feedback:event.target.value},'demo');
  });
  app.el('#defense-date').addEventListener('change',event=>{
    if(record&&!real)record=app.upsert({...record,reviewDate:event.target.value,noDate:false},'demo');
  });
  function decide(action){
    if(!record||real)return;
    const states={reject:['defense_rejected','rejected','Trabalho reprovado na demonstração.'],pending:['advisor_approved','pending','Aprovação com pendências registrada na demonstração.'],approve:['defense_approved','approved','Trabalho aprovado na demonstração.']};
    const [status,reviewDecision,message]=states[action];
    record=app.upsert({...record,status,reviewDecision,
      feedback:app.el('#review-feedback').value,reviewDate:app.el('#defense-date').value,noDate:app.el('#no-date').checked},'demo');
    app.toast(message);render();
  }
  app.el('#reject-button').addEventListener('click',()=>decide('reject'));
  app.el('#pending-button').addEventListener('click',()=>decide('pending'));
  app.el('#approve-button').addEventListener('click',()=>decide('approve'));
  const searchId=new URLSearchParams(location.search).get('id');
  if(searchId){await open(searchId)}
  else if(!real){const demoRecords=app.records('demo');if(demoRecords.length)await open((demoRecords.find(r=>r.status==='submitted')||demoRecords[0]).id)}
  render();
});
