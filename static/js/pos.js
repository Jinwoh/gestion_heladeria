(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const layout = document.querySelector(".pos-layout[data-cart-url]");
    if (!layout) return;

    const cartUrl = layout.dataset.cartUrl;
    const hasCaja = layout.dataset.hasCaja === "1";
    const cartItemsEl = document.getElementById("cart-items");
    const cartEmptyEl = document.getElementById("cart-empty");
    const cartFooterEl = document.getElementById("cart-footer");
    const totalVentaEl = document.getElementById("total-venta");
    const efectivoEl = document.getElementById("id_monto_efectivo");
    const tarjetaEl = document.getElementById("id_monto_tarjeta");
    const qrEl = document.getElementById("id_monto_qr");
    const totalCargadoEl = document.getElementById("total-cargado");
    const saldoPendienteEl = document.getElementById("saldo-pendiente");
    const vueltoEstimadoEl = document.getElementById("vuelto-estimado");
    const estadoPagoEl = document.getElementById("estado-pago");
    const btnConfirmar = document.getElementById("btn-confirmar-venta");
    const formPago = document.getElementById("form-pago-mixto");
    const csrfInput = document.querySelector("input[name='csrfmiddlewaretoken']");
    const csrfToken = csrfInput ? csrfInput.value : "";
    const numberFormatter = new Intl.NumberFormat("es-PY", {
      maximumFractionDigits: 0,
      minimumFractionDigits: 0,
    });

    function formatGs(value) {
      const number = Number(value || 0);
      return numberFormatter.format(Number.isFinite(number) ? Math.round(number) : 0) + "Gs";
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function numericValue(element) {
      return Number.parseFloat(element && element.value ? element.value : "0") || 0;
    }

    function currentTotal() {
      return Number.parseFloat(totalVentaEl.dataset.total || "0") || 0;
    }

    function updatePaymentSummary() {
      const totalVenta = currentTotal();
      const efectivo = numericValue(efectivoEl);
      const tarjeta = numericValue(tarjetaEl);
      const qr = numericValue(qrEl);
      const totalCargado = efectivo + tarjeta + qr;
      const saldoParaEfectivo = Math.max(totalVenta - tarjeta - qr, 0);
      const vuelto = efectivo > saldoParaEfectivo ? efectivo - saldoParaEfectivo : 0;
      const saldoPendiente = totalCargado < totalVenta ? totalVenta - totalCargado : 0;

      totalCargadoEl.textContent = formatGs(totalCargado);
      saldoPendienteEl.textContent = formatGs(saldoPendiente);
      vueltoEstimadoEl.textContent = formatGs(vuelto);

      if (totalCargado < totalVenta) {
        estadoPagoEl.textContent = "El monto cargado no alcanza para cubrir la venta.";
        btnConfirmar.disabled = true;
      } else if (tarjeta + qr > totalVenta) {
        estadoPagoEl.textContent = "Tarjeta y QR no pueden superar por sí solos el total.";
        btnConfirmar.disabled = true;
      } else {
        estadoPagoEl.textContent = "Pago válido para confirmar.";
        btnConfirmar.disabled = totalVenta <= 0;
      }
    }

    function updateStockIndicators(cartQuantities) {
      document.querySelectorAll(".stock-breakdown[data-product-id]").forEach(function (stockEl) {
        const productId = stockEl.dataset.productId;
        const stock = Number.parseInt(stockEl.dataset.stock || "0", 10);
        const cartQuantity = Number.parseInt(cartQuantities[productId] || "0", 10);
        const remaining = Math.max(stock - cartQuantity, 0);
        const cartEl = stockEl.querySelector(".stock-cart");
        const remainingEl = stockEl.querySelector(".stock-remaining");
        const row = stockEl.closest("tr");
        const input = row.querySelector(".pos-qty-input");
        const button = row.querySelector(".btn-add");

        stockEl.querySelector(".stock-cart-value").textContent = cartQuantity;
        stockEl.querySelector(".stock-remaining-value").textContent = remaining;
        cartEl.classList.toggle("is-hidden", cartQuantity === 0);
        remainingEl.classList.toggle("is-hidden", cartQuantity === 0);
        row.classList.toggle("pos-row-depleted", remaining === 0);

        input.max = String(remaining);
        input.disabled = !hasCaja || remaining === 0;
        button.disabled = !hasCaja || remaining === 0;
        button.classList.toggle("btn-add-disabled", button.disabled);
        if (remaining > 0 && numericValue(input) > remaining) input.value = "1";
      });
    }

    function cartItemMarkup(item) {
      const productId = Number.parseInt(item.producto_id, 10);
      const quantity = Number.parseInt(item.cantidad, 10);
      const stock = Number.parseInt(item.stock, 10);
      return `
        <div class="cart-item" data-cart-product-id="${productId}">
          <div class="cart-item-info">
            <span class="cart-item-name">${escapeHtml(item.nombre)}</span>
            <span class="cart-item-meta">${escapeHtml(item.categoria)} &nbsp;·&nbsp; ${formatGs(item.precio)} c/u</span>
          </div>
          <div class="cart-item-right">
            <span class="cart-item-subtotal">${formatGs(item.subtotal)}</span>
            <form method="post" class="cart-update-form">
              <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
              <input type="hidden" name="action" value="update">
              <input type="hidden" name="producto_id" value="${productId}">
              <input type="number" name="cantidad" min="0" max="${stock}" value="${quantity}" class="cart-qty-input">
              <button class="btn btn-sm" type="submit">OK</button>
            </form>
          </div>
        </div>`;
    }

    function renderCart(payload) {
      cartItemsEl.innerHTML = payload.items.map(cartItemMarkup).join("");
      const hasItems = payload.items.length > 0;
      cartEmptyEl.classList.toggle("is-hidden", hasItems);
      cartFooterEl.classList.toggle("is-hidden", !hasItems);
      totalVentaEl.dataset.total = payload.total;
      totalVentaEl.textContent = formatGs(payload.total);

      if (!hasItems) {
        efectivoEl.value = "0";
        tarjetaEl.value = "0";
        qrEl.value = "0";
      }

      updateStockIndicators(payload.cart_quantities || {});
      updatePaymentSummary();
    }

    function showFeedback(message, level) {
      let container = document.querySelector(".messages-floating");
      if (!container) {
        container = document.createElement("div");
        container.className = "messages messages-floating";
        document.querySelector("main.container").prepend(container);
      }

      const item = document.createElement("div");
      item.className = `msg ${level || "info"}`;
      item.innerHTML = `
        <div class="msg-content">
          <span class="msg-text">${escapeHtml(message)}</span>
          <button type="button" class="msg-close" aria-label="Cerrar">&times;</button>
        </div>`;
      container.appendChild(item);

      function dismiss() {
        item.classList.add("msg-hide");
        window.setTimeout(function () { item.remove(); }, 300);
      }
      item.querySelector(".msg-close").addEventListener("click", dismiss);
      window.setTimeout(dismiss, 3500);
    }

    async function submitCartAction(form) {
      const internalButton = form.querySelector("button[type='submit']");
      const externalButton = form.id
        ? document.querySelector(`button[form="${form.id}"]`)
        : null;
      const button = internalButton || externalButton;
      if (button) button.disabled = true;

      try {
        const response = await fetch(cartUrl, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken,
          },
        });
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          throw new Error("El servidor no devolvió una respuesta válida.");
        }

        const payload = await response.json();
        renderCart(payload);
        showFeedback(payload.message, payload.level);
        if (payload.ok && form.classList.contains("pos-add-form")) {
          const quantityInput = form.querySelector(".pos-qty-input");
          if (quantityInput && !quantityInput.disabled) quantityInput.value = "1";
        }
      } catch (error) {
        showFeedback(error.message || "No se pudo actualizar el carrito.", "error");
      } finally {
        if (button) {
          const row = button.closest("tr");
          const stockEl = row && row.querySelector(".stock-breakdown");
          const remaining = stockEl
            ? Number.parseInt(stockEl.querySelector(".stock-remaining-value").textContent || "0", 10)
            : 1;
          button.disabled = !hasCaja || remaining === 0;
        }
      }
    }

    document.addEventListener("submit", function (event) {
      const form = event.target;
      if (
        form.classList.contains("pos-add-form") ||
        form.classList.contains("cart-update-form") ||
        form.classList.contains("cart-clear-form")
      ) {
        event.preventDefault();
        submitCartAction(form);
      }
    });

    [efectivoEl, tarjetaEl, qrEl].forEach(function (element) {
      element.addEventListener("input", updatePaymentSummary);
    });

    formPago.addEventListener("submit", function (event) {
      const totalVenta = currentTotal();
      const efectivo = numericValue(efectivoEl);
      const tarjeta = numericValue(tarjetaEl);
      const qr = numericValue(qrEl);
      const totalCargado = efectivo + tarjeta + qr;

      if (totalCargado < totalVenta) {
        event.preventDefault();
        showFeedback("El monto pagado es menor al total de la venta.", "error");
      } else if (tarjeta + qr > totalVenta) {
        event.preventDefault();
        showFeedback("Tarjeta y QR no pueden superar el total de la venta.", "error");
      }
    });

    const btnToggleCliente = document.getElementById("btn-toggle-cliente");
    const panelClienteNuevo = document.getElementById("panel-cliente-nuevo");
    const inputClienteNuevo = document.getElementById("id_cliente_nuevo");
    const selectCliente = document.getElementById("id_cliente_id");

    btnToggleCliente.addEventListener("click", function () {
      const visible = panelClienteNuevo.style.display !== "none";
      panelClienteNuevo.style.display = visible ? "none" : "block";
      inputClienteNuevo.value = visible ? "0" : "1";
      btnToggleCliente.textContent = visible ? "Nuevo cliente" : "Cancelar alta rápida";
      if (!visible) selectCliente.value = "";
    });

    updatePaymentSummary();
  });
})();
