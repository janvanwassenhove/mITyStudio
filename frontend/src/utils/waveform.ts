// src/utils/waveform.ts

/**
 * Draws a waveform on a canvas element.
 * @param canvas HTMLCanvasElement
 * @param waveform Array of normalized values (0-1)
 * @param color Optional color (CSS string)
 */
export function drawWaveform(canvas: HTMLCanvasElement, waveform: number[], color: string = 'var(--primary)') {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.width
  const height = canvas.height

  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = color

  const barWidth = width / waveform.length

  waveform.forEach((value, index) => {
    const barHeight = value * height * 0.8
    const x = index * barWidth
    const y = (height - barHeight) / 2
    ctx.fillRect(x, y, barWidth - 1, barHeight)
  })
}
