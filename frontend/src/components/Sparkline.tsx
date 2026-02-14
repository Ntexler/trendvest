"use client";

interface Props {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  showDot?: boolean;
}

export default function Sparkline({
  data,
  color = "#22d3ee",
  width = 80,
  height = 28,
  showDot = true,
}: Props) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 3;

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const last = points[points.length - 1].split(",");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {showDot && (
        <circle
          cx={parseFloat(last[0])}
          cy={parseFloat(last[1])}
          r={2.5}
          fill={color}
        />
      )}
    </svg>
  );
}
