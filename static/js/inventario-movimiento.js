(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const productoSelect = document.getElementById("id_producto");
    const dataElement = document.getElementById("stock-por-producto");
    const stockCard = document.getElementById("stock-actual");
    const stockValue = document.getElementById("stock-actual-valor");
    const stockUnit = document.getElementById("stock-actual-unidad");

    if (!productoSelect || !dataElement || !stockCard || !stockValue) return;

    const stocks = JSON.parse(dataElement.textContent);

    function actualizarStockActual() {
      const productoId = productoSelect.value;
      if (!productoId) {
        stockCard.classList.add("is-hidden");
        stockValue.textContent = "0";
        if (stockUnit) stockUnit.textContent = "";
        return;
      }

      const item = stocks[productoId] || { stock: "0", unidad: "" };
      const cantidad = Number.parseFloat(item.stock);
      stockValue.textContent = Number.isFinite(cantidad)
        ? new Intl.NumberFormat("es-PY", { maximumFractionDigits: 3 }).format(cantidad)
        : "0";
      if (stockUnit) stockUnit.textContent = item.unidad || "";
      stockCard.classList.remove("is-hidden");
    }

    productoSelect.addEventListener("change", actualizarStockActual);
    actualizarStockActual();
  });
})();
