import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Button, Badge } from '@astryxdesign/core'

describe('Astryx + Tailwind v4 Smoke Test', () => {
  it('renders Astryx components with Tailwind utility classes', () => {
    render(
      <div className="bg-slate-900 p-4">
        <Badge
          label="Verified Ground Truth"
          className="font-semibold text-emerald-400"
        />
        <Button
          label="Launch Due Diligence"
          variant="primary"
          className="mt-2 text-white font-medium"
        />
      </div>
    )

    const badge = screen.getByTitle('Verified Ground Truth')
    expect(badge).toBeDefined()
    expect(badge.className).toContain('font-semibold')

    const button = screen.getByRole('button', { name: /Launch Due Diligence/i })
    expect(button).toBeDefined()
    expect(button.className).toContain('mt-2')
  })
})
