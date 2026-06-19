// Graficos simples em SVG puro, sem bibliotecas externas.

const COLORS = { Baixo: "#16a34a", Medio: "#d97706", Alto: "#dc2626" };

export function donutChart(distribuicao, size = 160) {
  const entries = Object.entries(distribuicao).filter(([, value]) => value > 0);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  const radius = size / 2;
  const stroke = size * 0.22;
  const innerRadius = radius - stroke / 2;
  const circumference = 2 * Math.PI * innerRadius;

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);

  if (total === 0) {
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", radius);
    circle.setAttribute("cy", radius);
    circle.setAttribute("r", innerRadius);
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", "#e2e8f0");
    circle.setAttribute("stroke-width", stroke);
    svg.appendChild(circle);
    return svg;
  }

  let offset = 0;
  entries.forEach(([key, value]) => {
    const fraction = value / total;
    const dash = fraction * circumference;
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", radius);
    circle.setAttribute("cy", radius);
    circle.setAttribute("r", innerRadius);
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", COLORS[key] || "#94a3b8");
    circle.setAttribute("stroke-width", stroke);
    circle.setAttribute("stroke-dasharray", `${dash} ${circumference - dash}`);
    circle.setAttribute("stroke-dashoffset", -offset);
    circle.setAttribute("transform", `rotate(-90 ${radius} ${radius})`);
    circle.setAttribute("stroke-linecap", entries.length > 1 ? "butt" : "round");
    svg.appendChild(circle);
    offset += dash;
  });

  const label = document.createElementNS(svgNS, "text");
  label.setAttribute("x", radius);
  label.setAttribute("y", radius - 2);
  label.setAttribute("text-anchor", "middle");
  label.setAttribute("font-size", size * 0.18);
  label.setAttribute("font-weight", "700");
  label.setAttribute("fill", "#0f172a");
  label.textContent = total;
  svg.appendChild(label);

  const sub = document.createElementNS(svgNS, "text");
  sub.setAttribute("x", radius);
  sub.setAttribute("y", radius + size * 0.13);
  sub.setAttribute("text-anchor", "middle");
  sub.setAttribute("font-size", size * 0.08);
  sub.setAttribute("fill", "#64748b");
  sub.textContent = "alunos";
  svg.appendChild(sub);

  return svg;
}

export function sparkline(values, width = 220, height = 48, color = "#4f46e5") {
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);

  if (!values || values.length === 0) return svg;

  const min = Math.min(...values, 0);
  const max = Math.max(...values, 10);
  const range = max - min || 1;
  const stepX = values.length > 1 ? width / (values.length - 1) : width;

  const points = values.map((value, index) => {
    const x = index * stepX;
    const y = height - ((value - min) / range) * (height - 6) - 3;
    return [x, y];
  });

  const path = document.createElementNS(svgNS, "path");
  const d = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point[0].toFixed(1)} ${point[1].toFixed(1)}`).join(" ");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", color);
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);

  points.forEach(([x, y], index) => {
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", index === points.length - 1 ? 3.2 : 2.2);
    circle.setAttribute("fill", color);
    svg.appendChild(circle);
  });

  return svg;
}

export function legendDot(color) {
  const span = document.createElement("span");
  span.style.display = "inline-block";
  span.style.width = "9px";
  span.style.height = "9px";
  span.style.borderRadius = "50%";
  span.style.background = color;
  span.style.marginRight = "6px";
  return span;
}

export { COLORS as riskColors };
