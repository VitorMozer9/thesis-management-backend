document.addEventListener('DOMContentLoaded',()=>{
  const app=window.TccApp;
  const real=app.mode()==='api';
  const form=app.el('#login-form');
  const note=app.el('#login-mode-notice');
  const button=app.el('#login-submit');
  const help=app.el('#login-help');
  if(real){
    note.textContent='Modo API real · autenticação não implementada';
    button.textContent='Acessar área de trabalhos';
    help.textContent='O backend atual não implementa login. Este botão abre as funcionalidades públicas existentes, sem autenticar usuários.';
    app.el('#institutional-login').disabled=true;
    app.el('#institutional-password').disabled=true;
  }
  form.addEventListener('submit',(event)=>{
    event.preventDefault();
    // Intencionalmente não enviar nem armazenar login/senha.
    location.href='publicados.html';
  });
});
