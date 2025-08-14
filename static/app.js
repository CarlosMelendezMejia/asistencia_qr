(function () {
  const form = document.getElementById("formRegistro");
  if (!form) return;

  const msg = document.getElementById("msg");

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
      const res = await fetch("/api/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        const err = (data && (data.error || data.message)) || `Error: ${res.status}`;
        msg.innerHTML = `<div class="alert alert-danger">${err}</div>`;
        return;
      }

      // Éxito
      msg.innerHTML = `<div class="alert alert-success">¡Asistencia registrada! 🎉</div>`;
      form.reset();
      // Si prefieres, redirige:
      // window.location.href = "/success";
    } catch (err) {
      msg.innerHTML = `<div class="alert alert-danger">Error de red: ${String(err)}</div>`;
    }
  });
})();
