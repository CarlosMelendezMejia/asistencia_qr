(function () {
  const form = document.getElementById("formRegistro");
  if (!form) return;

  const msg = document.getElementById("msg");
  const apiUrl = form.dataset.api;
  const successUrl = form.dataset.success;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.innerHTML = "";

    const formData = new FormData(form);
    // Valida mínimos
    const required = ["slug", "nombre", "apellidos", "email"];
    for (const r of required) {
      if (!formData.get(r)) {
        msg.innerHTML = `<div class="alert alert-warning">Falta: ${r}</div>`;
        return;
      }
    }

    // Prepara payload
    const payload = Object.fromEntries(formData.entries());
    payload["consentimiento"] = formData.get("consentimiento") ? 1 : 0;

    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        const text = await res.text();
        const errMsg = text || `Respuesta no JSON (Content-Type: ${contentType})`;
        msg.innerHTML = `<div class="alert alert-danger">${errMsg}</div>`;
        return;
      }
      const data = await res.json();

      if (!res.ok || !data.ok) {
        const err = (data && (data.error || data.message)) || `Error: ${res.status}`;
        msg.innerHTML = `<div class="alert alert-danger">${err}</div>`;
        return;
      }

      // Éxito
      msg.innerHTML = `<div class="alert alert-success">¡Asistencia registrada! 🎉</div>`;
      form.reset();
      if (successUrl) {
        window.location.href = successUrl;
        return;
      }
    } catch (err) {
      msg.innerHTML = `<div class="alert alert-danger">Error de red: ${String(err)}</div>`;
    }
  });
})();

(function () {
  const toggle = document.getElementById("themeToggle");
  if (!toggle) return;
  const root = document.documentElement;
  const body = document.body;

  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    body.setAttribute("data-theme", theme);
    toggle.innerHTML = theme === "dark" ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
  }

  let saved = localStorage.getItem("theme");
  if (!saved) {
    saved = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  setTheme(saved);

  toggle.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("theme", next);
  });
})();
