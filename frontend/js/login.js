"use strict";

const loginForm = document.querySelector("#login-form");

if (sessionActive()) location.replace(takeReturnPage());
else if (new URLSearchParams(location.search).get("session") === "expired") announce("Sua sessão expirou. Entre novamente.");

loginForm.addEventListener("submit", event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(loginForm));
  data.email = data.email.trim();
  loginForm.elements.password.value = "";
  run(async () => {
    try {
      const response = await api("identity", "/api/auth/login/", { method: "POST", body: data, auth: false });
      sessionStorage.setItem(sessionKey, response.access_token);
      await api("identity", "/api/auth/me/");
      location.replace(takeReturnPage());
    } catch (error) {
      sessionStorage.removeItem(sessionKey);
      if (error.status === 401) throw new Error("E-mail ou senha incorretos.");
      throw error;
    }
  });
});
