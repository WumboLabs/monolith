(function () {
  "use strict";

  const STORAGE_KEY = "monolith.workbench.tablePageSize.v2";
  const DEFAULT_PAGE_SIZE = 5;
  const MIN_ROWS_FOR_CONTROLS = 5;
  const PAGE_SIZE_OPTIONS = [5, 10, 15, 25, 50, 100, "all"];
  const TABLE_SELECTOR = "table";

  function getStoredPageSize() {
    const raw = localStorage.getItem(STORAGE_KEY);

    if (raw === "all") {
      return "all";
    }

    const parsed = Number.parseInt(raw || "", 10);

    if (PAGE_SIZE_OPTIONS.includes(parsed)) {
      return parsed;
    }

    return DEFAULT_PAGE_SIZE;
  }

  function setStoredPageSize(value) {
    localStorage.setItem(STORAGE_KEY, String(value));
  }

  function getTableRows(table) {
    const body = table.tBodies && table.tBodies.length ? table.tBodies[0] : null;

    if (!body) {
      return [];
    }

    return Array.from(body.rows);
  }

  function shouldSkipTable(table, rows) {
    if (table.dataset.noPagination === "true") {
      return true;
    }

    if (table.id === "hf-discovery-table") {
      return true;
    }

    if (table.closest("[data-no-pagination='true']")) {
      return true;
    }

    if (rows.length <= MIN_ROWS_FOR_CONTROLS) {
      return true;
    }

    return false;
  }

  function createButton(label, title) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workbench-table-button";
    button.textContent = label;
    button.title = title;
    return button;
  }

  function enhanceTable(table, index) {
    if (table.dataset.workbenchPaginated === "true") {
      return;
    }

    const rows = getTableRows(table);

    if (shouldSkipTable(table, rows)) {
      return;
    }

    table.dataset.workbenchPaginated = "true";

    const state = {
      page: 1,
      pageSize: getStoredPageSize(),
      rows,
    };

    const wrapper = document.createElement("div");
    wrapper.className = "workbench-table-wrap";

    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);

    const controls = document.createElement("div");
    controls.className = "workbench-table-controls";
    controls.setAttribute("aria-label", "Table pagination controls");

    const summary = document.createElement("div");
    summary.className = "workbench-table-summary";

    const pageSizeLabel = document.createElement("label");
    pageSizeLabel.className = "workbench-table-page-size";
    pageSizeLabel.textContent = "Rows ";

    const select = document.createElement("select");
    select.setAttribute("aria-label", "Rows per page");

    PAGE_SIZE_OPTIONS.forEach((option) => {
      const item = document.createElement("option");
      item.value = String(option);
      item.textContent = option === "all" ? "All" : String(option);
      select.appendChild(item);
    });

    select.value = String(state.pageSize);
    pageSizeLabel.appendChild(select);

    const pager = document.createElement("div");
    pager.className = "workbench-table-pager";

    const previous = createButton("Prev", "Previous page");
    const pageLabel = document.createElement("span");
    pageLabel.className = "workbench-table-page-label";
    const next = createButton("Next", "Next page");

    pager.appendChild(previous);
    pager.appendChild(pageLabel);
    pager.appendChild(next);

    controls.appendChild(summary);
    controls.appendChild(pageSizeLabel);
    controls.appendChild(pager);
    wrapper.insertBefore(controls, table);

    function pageSizeNumber() {
      return state.pageSize === "all" ? state.rows.length : Number(state.pageSize);
    }

    function pageCount() {
      if (state.pageSize === "all") {
        return 1;
      }

      return Math.max(1, Math.ceil(state.rows.length / pageSizeNumber()));
    }

    function render() {
      const totalPages = pageCount();

      if (state.page > totalPages) {
        state.page = totalPages;
      }

      const size = pageSizeNumber();
      const start = state.pageSize === "all" ? 0 : (state.page - 1) * size;
      const end = state.pageSize === "all" ? state.rows.length : start + size;

      state.rows.forEach((row, rowIndex) => {
        row.hidden = rowIndex < start || rowIndex >= end;
      });

      const firstVisible = state.rows.length === 0 ? 0 : start + 1;
      const lastVisible = Math.min(end, state.rows.length);

      summary.textContent = `Rows ${firstVisible}-${lastVisible} of ${state.rows.length}`;
      pageLabel.textContent = `Page ${state.page} / ${totalPages}`;

      previous.disabled = state.page <= 1;
      next.disabled = state.page >= totalPages;

      controls.dataset.pageSize = String(state.pageSize);
      controls.dataset.tableIndex = String(index);
    }

    select.addEventListener("change", () => {
      const value = select.value === "all" ? "all" : Number.parseInt(select.value, 10);
      state.pageSize = value;
      state.page = 1;
      setStoredPageSize(value);
      render();
    });

    previous.addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      render();
    });

    next.addEventListener("click", () => {
      state.page = Math.min(pageCount(), state.page + 1);
      render();
    });

    render();
  }

  function enhanceTables() {
    document.querySelectorAll(TABLE_SELECTOR).forEach((table, index) => {
      enhanceTable(table, index);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceTables);
  } else {
    enhanceTables();
  }
})();
