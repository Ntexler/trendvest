"use client";

interface Props {
  score: number;
  size?: "md" | "lg";
}

function getColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#eab308";
  return "#6b7280";
}

export default function HeatGauge({ score, size = "md" }: Props) {
  const dim = size === "lg" ? 86 : 44;
  const strokeWidth = size === "lg" ? 7 : 4;
  const radius = (dim - strokeWidth) / 2;
  const cx = dim / 2;
  const cy = dim / 2;

  // Arc from 135 to 405 degrees (270-degree sweep)
  const startAngle = 135;
  const endAngle = 405;
  const sweepAngle = (Math.min(100, Math.max(0, score)) / 100) * 270;

  const toRad = (deg: number) => (deg * Math.PI) / 180;

  const bgStart = {
    x: cx + radius * Math.cos(toRad(startAngle)),
    y: cy + radius * Math.sin(toRad(startAngle)),
  };
  const bgEnd = {
    x: cx + radius * Math.cos(toRad(endAngle)),
    y: cy + radius * Math.sin(toRad(endAngle)),
  };
  const valEnd = {
    x: cx + radius * Math.cos(toRad(startAngle + sweepAngle)),
    y: cy + radius * Math.sin(toRad(startAngle + sweepAngle)),
  };

  const bgLargeArc = 1;
  const valLargeArc = sweepAngle > 180 ? 1 : 0;

  const bgPath = `M ${bgStart.x} ${bgStart.y} A ${radius} ${radius} 0 ${bgLargeArc} 1 ${bgEnd.x} ${bgEnd.y}`;
  const valPath =
    sweepAngle > 0
      ? `M ${bgStart.x} ${bgStart.y} A ${radius} ${radius} 0 ${valLargeArc} 1 ${valEnd.x} ${valEnd.y}`
      : "";

  const color = getColor(score);
  const fontSize = size === "lg" ? 18 : 11;

  return (
    <svg width={dim} height={dim} viewBox={`0 0 ${dim} ${dim}`}>
      <path
        d={bgPath}
        fill="none"
        stroke="#1e293b"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {valPath && (
        <path
          d={valPath}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
      )}
      <text
        x={cx}
        y={cy + 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={color}
        fontSize={fontSize}
        fontWeight="bold"
        fontFamily="monospace"
      >
        {Math.round(score)}
      </text>
    </svg>
  );
}
