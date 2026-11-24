document.addEventListener('DOMContentLoaded',async()=>{
  const app=window.TccApp;
  const real=app.mode()==='api';
  const id=new URLSearchParams(location.search).get('id');
  const form=app.el('#thesis-form');
  const resultBox=app.el('#submission-result');
  const saveButton=app.el('#save-button');
  const submitButton=app.el('#submit-button');
  const fileInput=app.el('#thesis-file');
  let current=null;

  app.els('.api-only').forEach(node=>node.hidden=!real);
  app.els('.demo-only').forEach(node=>node.hidden=real);
  app.el('#advisor-note').textContent=real?'Nome guardado apenas neste navegador; não há endpoint para vincular o orientador.':'Informação de apresentação na demonstração.';
  app.showNotice(app.el('#submission-mode-note'),real
    ?'Modo API real: Salvar cria/atualiza um rascunho e pode enviar o PDF. O endpoint de submissão definitiva ainda não existe, por isso o botão Submeter está desativado.'
    :'Modo demonstração: dados e decisões ficam somente neste navegador. Salvar cria um rascunho; Submeter simula a mudança para análise.', 'info');
  if(real){
    submitButton.disabled=true;submitButton.title='Sem endpoint de submissão no backend atual.';
    app.el('#submit-footnote').textContent='A API atual não oferece endpoint para submissão, vinculação de orientador ou catálogo de cursos.';
  }
  if(id){
    try{
      current=real?await app.fetchThesis(id):app.getLocal(id);
      if(!current)throw new Error('Trabalho não encontrado no ambiente atual.');
      if(current.status!=='draft'){
        app.showNotice(app.el('#submission-mode-note'),'Esse trabalho não está em rascunho; o backend só permite editar ou enviar PDFs para trabalhos no status draft.','info');
        saveButton.disabled=true;submitButton.disabled=true;
      }
      app.el('#submission-page-title').textContent='Editar rascunho';
      app.el('#thesis-title').value=current.title||'';
      app.el('#thesis-abstract').value=current.abstract||'';
      app.el('#thesis-keywords').value=(current.keywords||[]).join(', ');
      app.el('#course-name').value=current.course||'Sistemas de Informação';
      app.el('#course-id').value=current.course_id||'';
      app.el('#student-id').value=current.student_id||'';
      app.el('#advisor-name').value=current.advisor||'';
      if(current.file_key||current.file_name){
        app.el('#file-hint').textContent=`Arquivo previamente associado: ${current.file_name||current.file_key}. Selecione outro PDF para substituí-lo.`;
      }
    }catch(error){
      app.toast(app.describeError(error),true);saveButton.disabled=true;submitButton.disabled=true;
      app.showNotice(app.el('#submission-mode-note'),`Não foi possível abrir o rascunho: ${app.describeError(error)}`,'error');
    }
  }
  fileInput.addEventListener('change',()=>{
    const file=fileInput.files?.[0];
    app.el('#upload-label').textContent=file?'Arquivo selecionado':'Enviar PDF';
    app.el('#upload-description').textContent=file?file.name:'Clique para selecionar até 20 MB';
    app.el('#file-hint').textContent=file?`${(file.size/1024/1024).toFixed(2)} MB · ${file.name}`:'Arquivo PDF, até 20 MB.';
  });

  async function validateFile(file){
    if(!file)return;
    if(!/\.pdf$/i.test(file.name))throw new Error('Selecione um arquivo com extensão .pdf.');
    if(file.size===0||file.size>20*1024*1024)throw new Error('O PDF deve ter entre 1 byte e 20 MB.');
    const sig=new Uint8Array(await file.slice(0,5).arrayBuffer());
    if(String.fromCharCode(...sig)!=='%PDF-')throw new Error('Arquivo inválido: assinatura %PDF- não encontrada.');
  }

  async function saveDraft(shouldSubmit=false){
    const title=app.el('#thesis-title').value.trim();
    const abstract=app.el('#thesis-abstract').value.trim();
    const keywordList=app.keywords(app.el('#thesis-keywords').value);
    const advisor=app.el('#advisor-name').value.trim();
    const course=app.el('#course-name').value.trim();
    const courseId=app.el('#course-id').value.trim();
    const studentId=app.el('#student-id').value.trim();
    const file=fileInput.files?.[0];
    if(!title)throw new Error('Informe o título do trabalho.');
    if(title.length>255)throw new Error('O título deve conter até 255 caracteres.');
    if(real && (!app.validUuid(courseId)||!app.validUuid(studentId)))throw new Error('Informe UUIDs válidos do curso e do aluno.');
    if(!real&&!course)throw new Error('Informe o curso.');
    await validateFile(file);
    if(shouldSubmit && (!abstract||keywordList.length===0||!advisor||!(file||current?.file_name)))
      throw new Error('Para simular a submissão, preencha resumo, orientador, palavras-chave e anexe um PDF.');

    if(!real){
      const record={...current,id:current?.id||app.uuid(),title,abstract,student_id:current?.student_id||app.uuid(),
        course_id:current?.course_id||app.uuid(),advisor,author:current?.author||'Aluno da demonstração',
        course,keywords:keywordList,status:shouldSubmit?'submitted':'draft',
        cover:current?.cover||2,year:new Date().getFullYear().toString(),
        file_name:file?.name||current?.file_name||null,reviewDecision:null};
      current=app.upsert(record,'demo');
      history.replaceState(null,'','submissao.html?id='+encodeURIComponent(current.id));
      app.showNotice(resultBox,shouldSubmit?'Submissão simulada: trabalho enviado para análise na demonstração.':'Rascunho salvo neste navegador.','success');
      app.toast(shouldSubmit?'Submissão demonstrativa concluída.':'Rascunho salvo localmente.');
      if(shouldSubmit){saveButton.disabled=true;submitButton.disabled=true;}
      return;
    }
    // Somente endpoints efetivamente existentes no repositório.
    let thesis;
    if(!current){
      thesis=await app.apiRequest('/theses/',{method:'POST',body:{title,abstract,student_id:studentId,course_id:courseId}});
      current=app.upsert({...thesis,advisor,keywords:[],file_name:null},'api');
      history.replaceState(null,'','submissao.html?id='+encodeURIComponent(current.id));
      app.showNotice(resultBox,`Rascunho criado na API. ID: ${current.id}. Continuando a atualização e o upload, se solicitado...`,'info');
    }else{
      thesis=await app.apiRequest(`/theses/${current.id}/`,{method:'PATCH',body:{title,abstract,keywords:keywordList}});
      current=app.upsert({...current,...thesis,advisor,keywords:keywordList},'api');
    }
    // A criação aceita title/abstract/student_id/course_id. Keywords são gravadas via PATCH.
    if(thesis && current && current.keywords?.length===0 && keywordList.length && !id){
      thesis=await app.apiRequest(`/theses/${current.id}/`,{method:'PATCH',body:{keywords:keywordList}});
      current=app.upsert({...current,...thesis,keywords:keywordList},'api');
    }
    if(file){
      const body=new FormData();body.append('file',file,file.name);
      thesis=await app.apiRequest(`/theses/${current.id}/pdf/`,{method:'POST',body});
      current=app.upsert({...current,...thesis,file_name:file.name},'api');
    }
    let uploadMessage='';
    if(file){
      try{
        const status=await app.apiRequest(`/theses/${current.id}/upload-status/`);
        uploadMessage=status.upload_status?` Status do upload: ${status.upload_status}.`:'';
      }catch{uploadMessage=' Não foi possível consultar o status do processamento.';}
    }
    app.showNotice(resultBox,`Rascunho salvo na API. ID: ${current.id}.${uploadMessage} O registro permanece em draft porque não existe endpoint de submissão.`, 'success');
    app.toast('Rascunho salvo na API.');
    app.el('#file-hint').textContent=file?'PDF enviado: '+file.name:'Rascunho salvo sem novo PDF.';
    fileInput.value='';
  }

  async function run(submit=false){
    if(saveButton.disabled|| (submit&&submitButton.disabled))return;
    saveButton.disabled=true;submitButton.disabled=true;
    saveButton.textContent='Salvando...';
    resultBox.hidden=true;
    try{await saveDraft(submit)}
    catch(error){app.showNotice(resultBox,`Não foi possível concluir: ${app.describeError(error)}${current?` O rascunho existente pode ser consultado pelo ID ${current.id}.`:''}`,'error');app.toast(app.describeError(error),true)}
    finally{
      saveButton.textContent='Salvar rascunho';
      if(!submit && (!current||current.status==='draft'))saveButton.disabled=false;
      if(!real && (!current||current.status==='draft'))submitButton.disabled=false;
    }
  }
  form.addEventListener('submit',event=>{event.preventDefault();run(false)});
  submitButton.addEventListener('click',()=>run(true));
});
