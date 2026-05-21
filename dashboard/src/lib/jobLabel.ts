export function jobTitle(kind: string | undefined, context?: Record<string, unknown>): string {
  if (!kind) return 'Job'
  if (kind === 'instance_start_wait') {
    const configId = context?.config_id
    const action = context?.action === 'switch' ? 'Switch instance' : 'Start instance'
    return typeof configId === 'string' && configId ? `${action}: ${configId}` : action
  }
  if (kind === 'model_pull') {
    const url = context?.url
    if (typeof url === 'string' && url) {
      const file = url.split('/').pop() ?? url
      return `Pull model: ${file}`
    }
    return 'Pull model'
  }
  return kind.replace(/_/g, ' ')
}

export function shortenUrl(url: string, max = 72): string {
  if (url.length <= max) return url
  const head = Math.floor(max * 0.55)
  const tail = max - head - 1
  return `${url.slice(0, head)}…${url.slice(-tail)}`
}
