import { readFile } from 'node:fs/promises'

import { describe, expect, it } from 'vitest'

describe('Docker frontend build context', () => {
  it('excludes Vite local environment overrides from production images', async () => {
    const dockerIgnore = await readFile('.dockerignore', 'utf8')
    const ignoredEntries = dockerIgnore
      .split(/\r?\n/)
      .map((entry) => entry.trim())
      .filter(Boolean)

    expect(ignoredEntries).toContain('.env.local')
    expect(ignoredEntries).toContain('.env.*.local')
  })

  it('does not ship external font stylesheets blocked by the production CSP', async () => {
    const html = await readFile('index.html', 'utf8')
    expect(html).not.toContain('fonts.googleapis.com')
    expect(html).not.toContain('fonts.gstatic.com')
  })
})
