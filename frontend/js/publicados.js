document.addEventListener('DOMContentLoaded',async()=>{
  const app=window.TccApp;
  const real=app.mode()==='api';
  const filters=[['author','author'],['title','title'],['course','course'],['advisor','advisor'],['year','year'],['keywords','keywords']];
  const inputs=Object.fromEntries(filters.map(([key])=>[key,app.el('#filter-'+key)]));
  const container=app.el('#thesis-list');
  const empty=app.el('#empty-state');
  const count=app.el('#results-count');
  if(real){
    app.showNotice(app.el('#repository-warning'),'A API ainda não possui listagem ou busca geral. Aqui aparecem somente trabalhos criados/consultados neste navegador. Use o UUID abaixo para abrir outros registros.','info');
    app.el('#repository-description').textContent='Consulte trabalhos já conhecidos pelo navegador ou abra diretamente pelo UUID.';
  }
  let all=app.records();
  function matches(record) {
    const norm=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    return filters.every(([key,property])=>{
      const query=norm(inputs[key].value.trim());
      if(!query)return true;
      const value=property==='keywords'?(record.keywords||[]).join(' '):record[property];
      return norm(value).includes(query);
    });
  }
  function render() {
    const visible=all.filter(matches);
    count.textContent=visible.length===1?'1 trabalho encontrado':`${visible.length} trabalhos encontrados`;
    container.innerHTML=visible.map((record,index)=>{
      const s=app.statusView(record);
      const cover=Number(record.cover)>=1 && Number(record.cover)<=3?record.cover:(index%3)+1;
      const author=record.author|| (real?'Aluno ID: '+String(record.student_id||'').slice(0,8)+'…':'Autores não informados');
      const meta=real?'Registro: '+record.id: `Orientação: ${record.advisor||'não informado'}${record.year?' · '+record.year:''}`;
      return `<article class="thesis-card">
        <img class="thesis-cover" src="assets/capa-${cover}.jpg" alt="Imagem ilustrativa do trabalho">
        <div class="thesis-card-body">
          <h3 class="thesis-card-title"><a href="banca.html?id=${encodeURIComponent(record.id)}">${app.escapeHtml(record.title||'Trabalho sem título')}</a> <span class="author-inline">– ${app.escapeHtml(author)}</span></h3>
          <p class="thesis-card-summary">${app.escapeHtml(record.abstract||'Nenhum resumo cadastrado.').slice(0,460)}</p>
          <div class="thesis-meta-row"><p class="thesis-meta">${app.escapeHtml(meta)}</p><span class="thesis-status status-${s.type}">${app.escapeHtml(s.label)} ${app.statusIcon(s.icon)}</span></div>
          <div class="card-actions"><a href="banca.html?id=${encodeURIComponent(record.id)}">Ver detalhes</a>${record.status==='draft'?`<a href="submissao.html?id=${encodeURIComponent(record.id)}">Editar rascunho</a>`:''}</div>
        </div></article>`;
    }).join('');
    empty.hidden=visible.length>0;
  }
  filters.forEach(([key])=>inputs[key].addEventListener('input',render));
  app.el('#clear-filters').addEventListener('click',()=>{Object.values(inputs).forEach(node=>node.value='');render()});
  app.el('#lookup-form').addEventListener('submit',async(event)=>{
    event.preventDefault();const id=app.el('#lookup-id').value.trim();
    if(!app.validUuid(id)){app.toast('Informe um UUID válido.',true);return}
    if(!real){
      if(!app.getLocal(id)){app.toast('Esse ID não existe na demonstração.',true);return}
      location.href='banca.html?id='+encodeURIComponent(id);return;
    }
    const button=event.target.querySelector('button');button.disabled=true;button.textContent='Consultando...';
    try{await app.fetchThesis(id);location.href='banca.html?id='+encodeURIComponent(id)}
    catch(error){app.toast(app.describeError(error),true)}
    finally{button.disabled=false;button.textContent='Consultar'}
  });
  render();
  if(real&&all.length){
    // Um GET por registro conhecido — nunca representar isso como listagem de toda a API.
    const results=await Promise.allSettled(all.slice(0,12).map(r=>app.fetchThesis(r.id)));
    const refreshed=results.filter(r=>r.status==='fulfilled').map(r=>r.value);
    const ids=new Set(refreshed.map(x=>x.id));
    all=[...refreshed,...all.filter(r=>!ids.has(r.id))];render();
  }
});
