(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("orden-form");
    const tipo = document.getElementById("id_tipo");
    const body = document.getElementById("detalle-body");
    const addButton = document.getElementById("agregar-linea");
    const template = document.getElementById("detalle-empty");
    const totalForms = document.getElementById("id_detalles-TOTAL_FORMS");
    const dataNode = document.getElementById("articulos-compra-data");
    if (!form || !tipo || !body || !dataNode) return;
    const articulos = JSON.parse(dataNode.textContent);
    const money = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 0 });

    function setupRow(row) {
      const product = row.querySelector('select[name$="-producto"]');
      const unit = row.querySelector('select[name$="-unidad_medida"]');
      const qty = row.querySelector('input[name$="-cantidad_solicitada"]');
      const cost = row.querySelector('input[name$="-costo_unitario"]');
      const remove = row.querySelector(".quitar-linea");
      function filterProducts() {
        if (!product) return;
        Array.from(product.options).forEach(function (option) {
          if (!option.value) return;
          option.hidden = Boolean(tipo.value && articulos[option.value] && articulos[option.value].tipo !== tipo.value);
        });
        if (product.value && articulos[product.value]?.tipo !== tipo.value) product.value = "";
        syncProduct();
      }
      function syncProduct() {
        const item = articulos[product?.value];
        if (item && unit) unit.value = String(item.unidad_id);
        if (item && cost && !cost.value && item.ultimo_costo) cost.value = item.ultimo_costo;
        updateTotal();
      }
      product?.addEventListener("change", syncProduct);
      qty?.addEventListener("input", updateTotal);
      cost?.addEventListener("input", updateTotal);
      remove?.addEventListener("click", function () { row.remove(); updateTotal(); });
      row.filterProducts = filterProducts;
      filterProducts();
    }

    function updateTotal() {
      let total = 0;
      body.querySelectorAll(".detalle-row").forEach(function (row) {
        const deleted = row.querySelector('input[name$="-DELETE"]')?.checked;
        const qty = Number.parseFloat(row.querySelector('input[name$="-cantidad_solicitada"]')?.value || 0);
        const cost = Number.parseFloat(row.querySelector('input[name$="-costo_unitario"]')?.value || 0);
        const subtotal = deleted ? 0 : qty * cost;
        const cell = row.querySelector(".subtotal-linea");
        if (cell) cell.textContent = `${money.format(Number.isFinite(subtotal) ? subtotal : 0)}Gs`;
        if (Number.isFinite(subtotal)) total += subtotal;
      });
      document.getElementById("orden-total").textContent = `${money.format(total)}Gs`;
    }

    body.querySelectorAll(".detalle-row").forEach(setupRow);
    tipo.addEventListener("change", function () { body.querySelectorAll(".detalle-row").forEach(row => row.filterProducts?.()); });
    addButton?.addEventListener("click", function () {
      const index = Number.parseInt(totalForms.value, 10);
      const holder = document.createElement("tbody");
      holder.innerHTML = template.innerHTML.replaceAll("__prefix__", String(index));
      const row = holder.firstElementChild;
      body.appendChild(row);
      totalForms.value = index + 1;
      setupRow(row);
    });
    updateTotal();
  });
})();
