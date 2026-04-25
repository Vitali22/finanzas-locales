function drawCharts() {
  const budget = document.getElementById("budgetChart");
  const category = document.getElementById("categoryChart");
  if (budget) new Chart(budget, { type: "bar", data: window.APP_DATA.budgetChart });
  if (category) new Chart(category, { type: "doughnut", data: window.APP_DATA.categoryChart });
}

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function renderCalendar() {
  const el = document.getElementById("calendar");
  const title = document.getElementById("calendarTitle");
  if (!el || !title) return;

  let current = new Date();
  const names = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"];

  async function load() {
    const key = monthKey(current);
    const response = await fetch(`/api/calendar?month=${key}`);
    const payload = await response.json();
    const eventsByDay = {};
    payload.events.forEach((event) => {
      eventsByDay[event.fecha] = eventsByDay[event.fecha] || [];
      eventsByDay[event.fecha].push(event);
    });

    const first = new Date(current.getFullYear(), current.getMonth(), 1);
    const last = new Date(current.getFullYear(), current.getMonth() + 1, 0);
    title.textContent = first.toLocaleDateString("es-MX", { month: "long", year: "numeric" });
    el.innerHTML = "";
    names.forEach((name) => {
      const cell = document.createElement("div");
      cell.className = "day-name";
      cell.textContent = name;
      el.appendChild(cell);
    });
    for (let i = 0; i < first.getDay(); i += 1) {
      el.appendChild(document.createElement("div"));
    }
    for (let day = 1; day <= last.getDate(); day += 1) {
      const cell = document.createElement("div");
      cell.className = "day-cell";
      const iso = `${key}-${String(day).padStart(2, "0")}`;
      cell.innerHTML = `<span class="day-number">${day}</span>`;
      (eventsByDay[iso] || []).forEach((event) => {
        const chip = document.createElement("span");
        chip.className = event.tipo === "gasto real" || event.tipo === "tarjeta" ? "event-chip real" : "event-chip";
        chip.title = `${event.nombre || "Movimiento"} $${Number(event.monto || 0).toFixed(2)}`;
        chip.textContent = `${event.nombre || "Movimiento"} $${Number(event.monto || 0).toFixed(0)}`;
        cell.appendChild(chip);
      });
      el.appendChild(cell);
    }
  }

  document.getElementById("prevMonth").addEventListener("click", () => {
    current = new Date(current.getFullYear(), current.getMonth() - 1, 1);
    load();
  });
  document.getElementById("nextMonth").addEventListener("click", () => {
    current = new Date(current.getFullYear(), current.getMonth() + 1, 1);
    load();
  });
  load();
}

function setupSubviewNavigation() {
  const links = Array.from(document.querySelectorAll("[data-view-link]"));
  const views = Array.from(document.querySelectorAll(".app-view"));
  const sections = Array.from(document.querySelectorAll(".section"));
  const gridGroups = Array.from(document.querySelectorAll(".grid.two"));

  function showView(viewId, updateUrl = true) {
    const target = document.getElementById(viewId) || document.getElementById("dashboard");
    if (!target) return;

    views.forEach((view) => {
      view.hidden = view !== target;
    });

    sections.forEach((section) => {
      const visibleView = Array.from(section.querySelectorAll(".app-view")).some((view) => !view.hidden);
      section.hidden = !visibleView;
    });

    gridGroups.forEach((grid) => {
      const childViews = Array.from(grid.children).filter((child) => child.classList.contains("app-view"));
      if (!childViews.length) return;
      const visibleChildren = childViews.filter((child) => !child.hidden);
      grid.hidden = visibleChildren.length === 0;
      grid.classList.toggle("single-view", visibleChildren.length === 1);
    });

    links.forEach((link) => {
      const isActive = link.dataset.viewLink === target.id;
      link.classList.toggle("active", isActive);
      if (isActive) {
        const group = link.closest("details");
        if (group) group.open = true;
      }
    });

    if (updateUrl) history.replaceState(null, "", `#${target.id}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  links.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showView(link.dataset.viewLink);
    });
  });

  const initial = window.location.hash ? window.location.hash.slice(1) : "dashboard";
  showView(initial, false);
}

document.addEventListener("DOMContentLoaded", () => {
  drawCharts();
  renderCalendar();
  setupSubviewNavigation();
});
