class LocalChart {
  constructor(canvas, config) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.type = config.type || "bar";
    this.data = config.data || [];
    this.draw();
    window.addEventListener("resize", () => this.draw());
  }

  setup() {
    const rect = this.canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(320, rect.width) * ratio;
    this.canvas.height = (this.canvas.getAttribute("height") || 220) * ratio;
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { width: this.canvas.width / ratio, height: this.canvas.height / ratio };
  }

  draw() {
    const { width, height } = this.setup();
    this.ctx.clearRect(0, 0, width, height);
    if (!this.data.length) {
      this.ctx.fillStyle = "#667085";
      this.ctx.fillText("Sin datos", 16, 28);
      return;
    }
    if (this.type === "doughnut") this.doughnut(width, height);
    else this.bar(width, height);
  }

  bar(width, height) {
    const max = Math.max(...this.data.map((d) => d.total), 1);
    const colors = ["#0f766e", "#94a3b8", "#2563eb", "#d97706", "#b42318"];
    const pad = 28;
    const gap = 18;
    const barW = (width - pad * 2 - gap * (this.data.length - 1)) / this.data.length;
    this.data.forEach((d, i) => {
      const h = ((height - 70) * d.total) / max;
      const x = pad + i * (barW + gap);
      const y = height - 38 - h;
      this.ctx.fillStyle = colors[i % colors.length];
      this.ctx.fillRect(x, y, barW, h);
      this.ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text") || "#18202a";
      this.ctx.font = "12px Arial";
      this.ctx.fillText(d.label, x, height - 18);
      this.ctx.fillText(`$${Number(d.total).toFixed(0)}`, x, Math.max(18, y - 7));
    });
  }

  doughnut(width, height) {
    const total = this.data.reduce((sum, d) => sum + Number(d.total || 0), 0) || 1;
    const colors = ["#0f766e", "#2563eb", "#d97706", "#b42318", "#7c3aed", "#0891b2"];
    const cx = Math.min(width * 0.34, 150);
    const cy = height / 2;
    const r = Math.min(height * 0.34, width * 0.22);
    let start = -Math.PI / 2;
    this.data.forEach((d, i) => {
      const angle = (Number(d.total || 0) / total) * Math.PI * 2;
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.arc(cx, cy, r, start, start + angle);
      this.ctx.closePath();
      this.ctx.fillStyle = colors[i % colors.length];
      this.ctx.fill();
      start += angle;
    });
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, r * 0.56, 0, Math.PI * 2);
    this.ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--surface") || "#fff";
    this.ctx.fill();

    this.ctx.font = "12px Arial";
    this.data.forEach((d, i) => {
      const y = 26 + i * 24;
      this.ctx.fillStyle = colors[i % colors.length];
      this.ctx.fillRect(width * 0.58, y - 10, 12, 12);
      this.ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text") || "#18202a";
      this.ctx.fillText(`${d.label}: $${Number(d.total).toFixed(0)}`, width * 0.58 + 18, y);
    });
  }
}

window.Chart = LocalChart;
