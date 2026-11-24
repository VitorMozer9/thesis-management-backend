import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = new URL("../js/", import.meta.url);
const source = name => readFileSync(fileURLToPath(new URL(name, root)), "utf8");

function loadScripts(...names) {
  const storage = new Map();
  const context = vm.createContext({
    URL, URLSearchParams, Headers, FormData, File, AbortSignal, console,
    atob: value => Buffer.from(value, "base64").toString("binary"),
    location: { origin: "http://127.0.0.1:8080", pathname: "/banca.html", search: "?id=1", replace() {} },
    document: { querySelector: () => null },
    sessionStorage: {
      getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value)),
      removeItem: key => storage.delete(key)
    }
  });
  vm.runInContext(source("config.js") + "\n" + source("core.js"), context);
  vm.runInContext("start = () => {};", context);
  for (const name of names) vm.runInContext(source(name), context);
  return context;
}

test("schedule payload sends only the filled location field", () => {
  const context = loadScripts("banca.js");
  const base = { starts_at: "2030-05-10T14:00", ends_at: "2030-05-10T15:00" };
  const venueBody = context.scheduleBody({ ...base, venue: " Sala 2 ", meeting_url: "" });
  assert.equal(venueBody.venue, "Sala 2");
  assert.equal("meeting_url" in venueBody, false);
  const onlineBody = context.scheduleBody({ ...base, venue: "", meeting_url: "https://meet.example/abc" });
  assert.equal("venue" in onlineBody, false);
  assert.throws(() => context.scheduleBody({ ...base, venue: "Sala", meeting_url: "https://x.example" }));
  assert.throws(() => context.scheduleBody({ ...base, venue: "", meeting_url: "http://x.example" }));
  assert.throws(() => context.scheduleBody({ ...base, ends_at: base.starts_at, venue: "Sala", meeting_url: "" }));
});

test("validation details are translated and labelled", () => {
  const context = loadScripts();
  assert.equal(context.validationDetails({ title: ["This field may not be blank."] }), "Título: preencha este campo.");
  assert.equal(context.validationDetails({ detail: "A PDF must be attached before submission." }), "Envie o PDF antes de submeter.");
  assert.equal(context.validationDetails({ detail: "Informe somente o local ou o link da reunião." }), "Informe somente o local ou o link da reunião.");
});

test("return page after login accepts only local pages", () => {
  const context = loadScripts();
  context.sessionStorage.setItem("ufvjm.return", "banca.html?id=abc-1");
  assert.equal(context.takeReturnPage(), "banca.html?id=abc-1");
  for (const unsafe of ["https://evil.example/x.html", "//evil.example/a.html", "javascript:alert(1)", "../painel.html"]) {
    context.sessionStorage.setItem("ufvjm.return", unsafe);
    assert.equal(context.takeReturnPage(), "painel.html");
  }
});

test("submission requirements mirror the thesis domain rules", () => {
  const context = loadScripts("submissao.js");
  const missing = context.submissionRequirements({ abstract: " ", keywords: [], advisor_id: null, file_key: null, file_sha256: null });
  assert.equal(missing.every(([, done]) => !done), true);
  const ready = context.submissionRequirements({ abstract: "Resumo", keywords: ["a"], advisor_id: "x", file_key: "k", file_sha256: "h" });
  assert.equal(ready.every(([, done]) => done), true);
});

test("pagination is omitted when there is a single page", () => {
  const context = loadScripts();
  assert.equal(context.pagination(1, false, () => {}), null);
});
