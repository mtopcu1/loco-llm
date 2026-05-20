interface SparklineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
}

export function Sparkline({
  values,
  width = 120,
  height = 32,
  color = 'currentColor',
}: SparklineProps) {
  if (values.length < 2) return <svg width={width} height={height} />
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const xStep = width / (values.length - 1)
  const points = values
    .map((v, i) => `${i * xStep},${height - ((v - min) / range) * height}`)
    .join(' ')
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
    </svg>
  )
}
