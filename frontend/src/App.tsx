import { Button, Badge } from '@astryxdesign/core'

export function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col items-center justify-center">
      <div className="max-w-md w-full bg-slate-800 rounded-xl p-6 shadow-xl border border-slate-700 space-y-4">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          GujRERA Analyst Workbench
        </h1>
        <p className="text-slate-400 text-sm">
          Sovereign quantitative diligence & forensic agent runtime
        </p>
        <div className="flex items-center gap-3">
          <Badge label="Truth Grounded" className="font-semibold text-emerald-400" />
          <Button
            label="Launch Due Diligence"
            variant="primary"
            className="px-4 py-2 font-medium"
          />
        </div>
      </div>
    </div>
  )
}

export default App
