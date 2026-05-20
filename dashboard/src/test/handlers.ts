import { http, HttpResponse } from 'msw'

const overviewPayload = {
  version: { cli_version: '1.1.0' },
  instance: { running: false },
  runtimes_count: 2,
  runtimes_installed_count: 1,
  models_count: 3,
  configs_count: 5,
  doctor_summary: {
    default: { ok: 4, warning: 0, error: 0 },
    runtime: { ok: 2, warning: 1, error: 0 },
    dashboard: { ok: 3, warning: 0, error: 0 },
  },
  recent_history: [],
  disk_summary: { data_root_pct_used: 42, models_count: 3, cache_bytes: 1024 },
}

const runtimesList = [
  {
    id: 'vllm',
    kind: 'official',
    installed: true,
    installed_at: '2026-01-01T00:00:00Z',
    has_metrics: false,
  },
  {
    id: 'stub-runtime',
    kind: 'official',
    installed: true,
    installed_at: '2026-01-01T00:00:00Z',
    has_metrics: false,
  },
  {
    id: 'llama.cpp',
    kind: 'official',
    installed: false,
    installed_at: null,
    has_metrics: false,
  },
]

const stubRuntimeDetail = {
  id: 'stub-runtime',
  kind: 'official',
  installed: true,
  manifest: { id: 'stub-runtime', kind: 'official', accepts_formats: [] },
  install_record: { installed_at: '2026-01-01T00:00:00Z', cli_version: '1.0.0' },
  drift: null,
}

const runtimeDetail = {
  id: 'vllm',
  kind: 'official',
  installed: true,
  manifest: { id: 'vllm', kind: 'official', version: '1.0' },
  install_record: { installed_at: '2026-01-01T00:00:00Z', cli_version: '1.0.0' },
  drift: null,
}

const modelsList = [
  {
    id: 'llama-3',
    format: 'gguf',
    source: { kind: 'hf', repo: 'meta/llama', revision: 'main' },
    artifact: { primary: 'model.gguf', files: ['model.gguf'], total_size_bytes: 4_000_000_000 },
    metadata: { display_name: 'Llama 3' },
    installed_at: '2026-01-01T00:00:00Z',
  },
]

const modelDetail = modelsList[0]

const configsList = [
  { id: 'default', source: 'user', data: { runtime: 'vllm', serve: { params: { port: '8000' } } } },
]

const configDetail = {
  id: 'default',
  source: 'user',
  raw: { runtime: 'vllm', serve: { params: { port: '8000' } } },
  resolved: { runtime: 'vllm', serve: { params: { port: '8000' } } },
}

const configParams = [
  {
    key: 'host',
    label: 'Host',
    description: 'Bind host',
    value: '127.0.0.1',
    enabled: true,
    locked: true,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
  },
  {
    key: 'port',
    label: 'Port',
    description: 'HTTP port',
    value: '8000',
    enabled: true,
    locked: false,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
  },
]

const defaultParams = [
  {
    key: 'host',
    label: 'Host',
    description: 'Bind host',
    value: '127.0.0.1',
    enabled: true,
    locked: true,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
  },
  {
    key: 'port',
    label: 'Port',
    description: 'HTTP port',
    value: '',
    enabled: false,
    locked: false,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
  },
]

const recommendationsPayload = [
  {
    param_key: 'port',
    suggested_value: '8080',
    reason: 'Common alternate port',
    confidence: 0.8,
  },
]

const doctorPayload = {
  scopes: {
    default: [{ name: 'python', status: 'ok', message: 'detected=3.11' }],
    runtime: [{ name: 'cuda', status: 'warning', message: 'not found' }],
    dashboard: [{ name: 'node', status: 'ok', message: 'detected=20.0' }],
  },
}

const diskPayload = {
  data_root: '/data',
  data_root_bytes_total: 1_000_000_000_000,
  data_root_bytes_used: 420_000_000_000,
  data_root_bytes_free: 580_000_000_000,
  cache_bytes: 1024,
  models: [{ id: 'llama-3', bytes: 4_000_000_000 }],
}

const historyPayload = {
  items: [
    { ts: '2026-01-01T12:00:00Z', action: 'start', config_id: 'default', id: 'default' },
    { ts: '2026-01-01T13:00:00Z', action: 'stop', config_id: 'default', id: 'default' },
  ],
  total: 2,
  limit: 25,
  offset: 0,
}

const settingsPayload = {
  stored: { data_root: '~/llm-data' },
  resolved: {
    data_root: '/home/user/llm-data',
    repo_root: '/home/user/scaffold',
    runtimes_dir: '/home/user/llm-data/runtimes',
    models_dir: '/home/user/llm-data/models',
    cache_dir: '/home/user/llm-data/cache',
  },
  registry: [
    { key: 'data_root', kind: 'path', label: 'Data root' },
    { key: 'repo_root', kind: 'path', label: 'Repo root' },
  ],
}

export const handlers = [
  http.get('http://localhost/api/overview', () => HttpResponse.json(overviewPayload)),
  http.get('http://localhost/api/version', () => HttpResponse.json({ cli_version: '1.1.0' })),
  http.get('http://localhost/api/instance', () => HttpResponse.json({ running: false })),
  http.get('http://localhost/api/runtimes', () => HttpResponse.json(runtimesList)),
  http.get('http://localhost/api/runtimes/:id', ({ params }) => {
    if (params.id === 'vllm') return HttpResponse.json(runtimeDetail)
    if (params.id === 'stub-runtime') return HttpResponse.json(stubRuntimeDetail)
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/runtimes/:id/default-params', ({ params }) => {
    if (params.id === 'vllm' || params.id === 'stub-runtime') {
      return HttpResponse.json(defaultParams)
    }
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/recommendations', () =>
    HttpResponse.json(recommendationsPayload),
  ),
  http.get('http://localhost/api/models', () => HttpResponse.json(modelsList)),
  http.get('http://localhost/api/models/:id', ({ params }) => {
    if (params.id === 'llama-3') return HttpResponse.json(modelDetail)
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/configs', () => HttpResponse.json(configsList)),
  http.get('http://localhost/api/configs/:id', ({ params }) => {
    if (params.id === 'default') return HttpResponse.json(configDetail)
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/configs/:id/params', ({ params }) => {
    if (params.id === 'default') return HttpResponse.json(configParams)
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/configs/:id/validate', ({ params }) => {
    if (params.id === 'default') return HttpResponse.json({ valid: true, errors: [] })
    return HttpResponse.json({ error: 'not found' }, { status: 404 })
  }),
  http.get('http://localhost/api/doctor', () => HttpResponse.json(doctorPayload)),
  http.get('http://localhost/api/disk', () => HttpResponse.json(diskPayload)),
  http.get('http://localhost/api/history', () => HttpResponse.json(historyPayload)),
  http.get('http://localhost/api/settings', () => HttpResponse.json(settingsPayload)),
  http.get('http://localhost/api/jobs', () => HttpResponse.json([])),
  http.get('http://localhost/api/jobs/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id,
      kind: 'runtime_install',
      status: 'running',
      created_at: '2026-01-01T00:00:00Z',
      context: { runtime_id: 'vllm' },
    }),
  ),
  http.post('http://localhost/api/jobs/:id/cancel', () =>
    HttpResponse.json({ cancelled: true }),
  ),
  http.post('http://localhost/api/runtimes/:id/install', () =>
    HttpResponse.json({ job_id: 'job-install' }),
  ),
  http.post('http://localhost/api/runtimes/:id/rebuild', () =>
    HttpResponse.json({ job_id: 'job-rebuild' }),
  ),
  http.delete('http://localhost/api/runtimes/:id', () => HttpResponse.json({ ok: true })),
  http.post('http://localhost/api/models/pull', () =>
    HttpResponse.json({ job_id: 'job-pull' }),
  ),
  http.post('http://localhost/api/models/add', () => HttpResponse.json({ ok: true })),
  http.delete('http://localhost/api/models/:id', () => HttpResponse.json({ ok: true })),
  http.post('http://localhost/api/configs', () => HttpResponse.json({ id: 'new-cfg' })),
  http.put('http://localhost/api/configs/:id', () => HttpResponse.json({ id: 'default' })),
  http.delete('http://localhost/api/configs/:id', () => HttpResponse.json({ ok: true })),
  http.post('http://localhost/api/instance/start', () =>
    HttpResponse.json({ job_id: 'job-start' }),
  ),
  http.post('http://localhost/api/instance/stop', () => HttpResponse.json({ ok: true })),
  http.post('http://localhost/api/instance/switch', () =>
    HttpResponse.json({ job_id: 'job-switch' }),
  ),
  http.put('http://localhost/api/settings/:key', () => HttpResponse.json(settingsPayload)),
]
