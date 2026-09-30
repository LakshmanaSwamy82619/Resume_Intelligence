import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'

const lines = [['92%'], ['78%', '54%', '0'], ['86%'], ['64%', '100%', '1.6s'], ['90%'], ['70%', '68%', '3.1s'], ['84%'], ['52%']]

function useCountUp(target, ms = 1800) {
  const [n, setN] = useState(0)
  useEffect(() => {
    let raf, t0
    const step = (t) => { t0 ??= t; const p = Math.min((t - t0) / ms, 1); setN(Math.round(target * (1 - Math.pow(1 - p, 3)))); if (p < 1) raf = requestAnimationFrame(step) }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return n
}

export default function ResumeScan() {
  const score = useCountUp(94)
  return <div className="scan" aria-hidden="true">
    <div className="scan-doc">
      <div className="scan-head"><span className="scan-avatar" /><div><div className="scan-name" /><div className="scan-role" /></div></div>
      {lines.map(([w, hl, d], i) => <div key={i} className={`scan-line ${hl ? 'hl' : ''}`} style={{ width: w, '--w': hl || 0, '--d': d }} />)}
      <div className="scan-beam" />
    </div>
    <div className="scan-tag">Evidence found in 3 places</div>
    <div className="scan-score"><Check size={18} color="#ffb547" /><div><strong>{score}%</strong><small>Requirement match</small></div></div>
  </div>
}
