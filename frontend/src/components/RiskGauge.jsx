// frontend/src/components/RiskGauge.jsx
export default function RiskGauge({ score }) {
  // ✅ Vérifier que score est un nombre valide
  const validScore = typeof score === 'number' && !isNaN(score) ? score : 0
  
  // ✅ Forcer score entre 0 et 100
  const clampedScore = Math.max(0, Math.min(100, validScore))
  
  // ✅ Couleurs en fonction du score
  const color = clampedScore < 40 ? "#22c55e"   // Vert
              : clampedScore < 65 ? "#f59e0b"   // Orange
              : "#ef4444"                       // Rouge
  
  const strokeDash = clampedScore * 2.83

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 110" className="w-48">
        {/* Fond */}
        <path 
          d="M10 100 A90 90 0 0 1 190 100" 
          fill="none" 
          stroke="#1f2937" 
          strokeWidth="20"
        />
        {/* Jauge */}
        <path 
          d="M10 100 A90 90 0 0 1 190 100" 
          fill="none" 
          stroke={color}
          strokeWidth="20" 
          strokeDasharray={`${strokeDash} 283`}
          strokeLinecap="round"
        />
        {/* Score */}
        <text 
          x="100" 
          y="95" 
          textAnchor="middle" 
          fill="white" 
          fontSize="28" 
          fontWeight="bold"
        >
          {clampedScore}%
        </text>
        <text 
          x="100" 
          y="112" 
          textAnchor="middle" 
          fill="#9ca3af" 
          fontSize="11"
        >
          Risk Score
        </text>
      </svg>
      
      {/* ✅ Affichage du niveau de risque */}
      <div className="mt-2 text-sm font-medium" style={{ color }}>
        {clampedScore < 40 ? "🟢 Faible" : 
         clampedScore < 65 ? "🟡 Modéré" : 
         "🔴 Élevé"}
      </div>
    </div>
  )
}