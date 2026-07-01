import { useState } from "react"
import axios from "axios"
import RiskGauge from "../components/RiskGauge"

const US_STATES = ["AL","AR","AZ","CA","CO","CT","DC","DE","FL","GA",
  "IA","ID","IL","IN","KS","KY","LA","MA","MD","ME","MI","MN","MO",
  "MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY","OH","OK","OR",
  "PA","RI","SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY"]

const WEATHER_CONDITIONS = ["Fair","Clear","Mostly Cloudy","Partly Cloudy",
  "Overcast","Light Rain","Rain","Heavy Rain","Light Snow","Snow",
  "Fog","Thunderstorm","Haze","Drizzle","Cloudy","Other"]

export default function Predict() {
  const now = new Date()
  const currentHour = now.getHours()
  const currentDay = now.getDay()

  const [form, setForm] = useState({
    Start_Lat: 39.865147,
    Start_Lng: -84.058723,
    State: "OH",
    City: "Dayton",
    
    Temperature: 55,
    Humidity: 50,
    Pressure: 29.9,
    Visibility: 10,
    Precipitation: 0,
    Wind_Speed: 5,
    Weather_Condition: "Clear",
    
    Hour: currentHour,
    Month: now.getMonth() + 1,
    DayOfWeek: currentDay,
    IsWeekend: (currentDay === 5 || currentDay === 6) ? 1 : 0,
    IsRushHour: ([7,8,9,16,17,18,19].includes(currentHour)) ? 1 : 0,
    
    Junction: 0,
    Traffic_Signal: 0,
    Crossing: 0,
    Bump: 0,
    
    mode: "standard"
  })

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function getSeason(month) {
    if (month >= 3 && month <= 5) return "Spring"
    if (month >= 6 && month <= 8) return "Summer"
    if (month >= 9 && month <= 11) return "Fall"
    return "Winter"
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setForm(prev => ({
      ...prev,
      [name]: type === "checkbox" ? (checked ? 1 : 0) :
              ["Start_Lat","Start_Lng","Temperature","Humidity",
               "Pressure","Visibility","Precipitation","Wind_Speed",
               "Hour","Month","DayOfWeek","IsWeekend","IsRushHour"].includes(name)
              ? parseFloat(value) : value
    }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const payload = {
        Start_Lat: parseFloat(form.Start_Lat) || 39.865147,
        Start_Lng: parseFloat(form.Start_Lng) || -84.058723,
        State: form.State || "OH",
        City: form.City || "Unknown",
        
        Temperature_F: parseFloat(form.Temperature) || 55,
        Humidity: parseFloat(form.Humidity) || 50,
        Pressure: parseFloat(form.Pressure) || 29.9,
        Visibility_mi: parseFloat(form.Visibility) || 10,
        Precipitation_in: parseFloat(form.Precipitation) || 0,
        Wind_Speed_mph: parseFloat(form.Wind_Speed) || 5,
        Weather_Condition: form.Weather_Condition || "Clear",
        
        Hour: parseInt(form.Hour) || 12,
        Month: parseInt(form.Month) || 6,
        DayOfWeek: parseInt(form.DayOfWeek) || 3,
        IsWeekend: parseInt(form.IsWeekend) || 0,
        IsRushHour: parseInt(form.IsRushHour) || 0,
        
        Junction: parseInt(form.Junction) || 0,
        Traffic_Signal: parseInt(form.Traffic_Signal) || 0,
        Crossing: parseInt(form.Crossing) || 0,
        Bump: parseInt(form.Bump) || 0,
        
        mode: form.mode || "standard"
      }
      
      console.log("📤 Payload envoyé :", JSON.stringify(payload, null, 2))
      
      const res = await axios.post("http://localhost:8000/predict", payload)
      console.log("📥 Réponse reçue :", res.data)
      
      // ✅ Utiliser les données reçues
      if (res.data && typeof res.data.risk_score === 'number') {
        // Construire l'objet result avec toutes les valeurs
        const data = {
          risk_score: res.data.risk_score || 0,
          risk_level: res.data.risk_level || "Inconnu",
          threshold_used: res.data.threshold_used || 0.65,
          is_high_risk: res.data.is_high_risk || false,
          explanation: res.data.explanation || "",
          // probability = risk_score / 100
          probability: (res.data.risk_score || 0) / 100
        }
        console.log("📊 Données à afficher :", data)
        setResult(data)
      } else {
        throw new Error("Réponse invalide du serveur")
      }
      
    } catch (err) {
      console.error("❌ Erreur :", err.response?.data || err.message)
      if (err.response?.data?.detail) {
        console.log("📋 Détails de validation :")
        err.response.data.detail.forEach(d => {
          console.log(`  - ${d.loc.join('.')} : ${d.msg}`)
        })
        setError(`Erreur: ${err.response.data.detail[0]?.msg || 'Validation error'}`)
      } else {
        setError("Erreur API — Vérifie que FastAPI tourne sur le port 8000")
      }
    }
    setLoading(false)
  }

  // ✅ Utiliser result pour les calculs
  const riskScore = result ? Math.round(result.risk_score) : 0
  const riskLevel = result?.risk_level || "unknown"
  
  const riskColor = riskLevel === "Faible" ? "text-green-400" :
                    riskLevel === "Modéré" ? "text-yellow-400" :
                    riskLevel === "Élevé" ? "text-orange-400" :
                    riskLevel === "Très élevé" ? "text-red-400" : "text-gray-400"

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <h2 className="text-3xl font-bold mb-8 text-center">Trip Risk Analysis</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* LEFT — Form */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
          <h3 className="font-semibold text-blue-400 mb-2">📍 Location</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400">Latitude</label>
              <input type="number" name="Start_Lat" value={form.Start_Lat}
                onChange={handleChange} step="0.001"
                className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1"/>
            </div>
            <div>
              <label className="text-xs text-gray-400">Longitude</label>
              <input type="number" name="Start_Lng" value={form.Start_Lng}
                onChange={handleChange} step="0.001"
                className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1"/>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400">State</label>
              <select name="State" value={form.State} onChange={handleChange}
                className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1">
                {US_STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400">City</label>
              <input type="text" name="City" value={form.City}
                onChange={handleChange}
                className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1"/>
            </div>
          </div>

          <h3 className="font-semibold text-blue-400 mt-4 mb-2">🌤️ Weather</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Temperature (°F)", "Temperature"],
              ["Humidity (%)", "Humidity"],
              ["Pressure (in)", "Pressure"],
              ["Visibility (mi)", "Visibility"],
              ["Precipitation (in)", "Precipitation"],
              ["Wind Speed (mph)", "Wind_Speed"]
            ].map(([label, name]) => (
              <div key={name}>
                <label className="text-xs text-gray-400">{label}</label>
                <input type="number" name={name} value={form[name] || 0}
                  onChange={handleChange} step="0.1"
                  className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1"/>
              </div>
            ))}
          </div>
          <div>
            <label className="text-xs text-gray-400">Weather Condition</label>
            <select name="Weather_Condition" value={form.Weather_Condition}
              onChange={handleChange}
              className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1">
              {WEATHER_CONDITIONS.map(w => <option key={w}>{w}</option>)}
            </select>
          </div>

          <h3 className="font-semibold text-blue-400 mt-4 mb-2">🕐 Time</h3>
          <div className="grid grid-cols-3 gap-3">
            {[["Hour (0-23)", "Hour"], ["Month (1-12)", "Month"], ["Day (0=Mon)", "DayOfWeek"]].map(([label, name]) => (
              <div key={name}>
                <label className="text-xs text-gray-400">{label}</label>
                <input type="number" name={name} value={form[name]}
                  onChange={handleChange} min="0" max={name === "Hour" ? 23 : name === "Month" ? 12 : 6}
                  className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm mt-1"/>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" name="IsWeekend" checked={form.IsWeekend === 1}
                onChange={() => setForm(p => ({...p, IsWeekend: p.IsWeekend ? 0 : 1}))} className="w-4 h-4"/>
              Weekend
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" name="IsRushHour" checked={form.IsRushHour === 1}
                onChange={() => setForm(p => ({...p, IsRushHour: p.IsRushHour ? 0 : 1}))} className="w-4 h-4"/>
              Rush Hour
            </label>
          </div>

          <h3 className="font-semibold text-blue-400 mt-4 mb-2">🛣️ Road Features</h3>
          <div className="flex flex-wrap gap-4">
            {[
              ["Junction", "Junction"],
              ["Traffic Signal", "Traffic_Signal"],
              ["Crossing", "Crossing"],
              ["Bump", "Bump"]
            ].map(([label, name]) => (
              <label key={name} className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" name={name} checked={form[name] === 1}
                  onChange={handleChange} className="w-4 h-4"/>
                {label}
              </label>
            ))}
          </div>

          <h3 className="font-semibold text-blue-400 mt-4 mb-2">⚙️ Mode</h3>
          <div className="flex gap-3">
            {["standard", "pro", "strict"].map(m => (
              <button key={m} onClick={() => setForm(p => ({...p, mode: m}))}
                className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition
                  ${form.mode === m ? "bg-blue-600" : "bg-gray-800 hover:bg-gray-700"}`}>
                {m}
              </button>
            ))}
          </div>

          <button onClick={handleSubmit} disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
              py-3 rounded-xl font-semibold mt-4 transition">
            {loading ? "Analyzing..." : "Analyze Trip Risk →"}
          </button>

          {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        </div>

        {/* RIGHT — Result */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 flex flex-col items-center justify-center">
          {!result ? (
            <div className="text-center text-gray-500">
              <div className="text-6xl mb-4">🛡️</div>
              <p>Fill in the form and click<br/>"Analyze Trip Risk" to get your risk score</p>
            </div>
          ) : (
            <div className="w-full space-y-6">
              <RiskGauge score={riskScore} />
              <div className="text-center">
                <div className={`text-2xl font-bold ${riskColor}`}>
                  {riskLevel} Risk
                </div>
                <div className="text-gray-400 text-sm mt-1">
                  {result.is_high_risk ? "⚠️ High risk detected" : "✅ Safe to drive"}
                </div>
              </div>
              <div className="bg-gray-800 rounded-xl p-4 text-sm text-gray-300">
                <p>Risk Score: {result.risk_score}%</p>
                <p>Threshold used: {result.threshold_used}</p>
                <p>Mode: {result.mode}</p>
                <p className="mt-2">{result.explanation}</p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-800 rounded-lg p-3">
                  <div className="text-gray-400">Risk Score</div>
                  <div className="font-bold text-lg">{result.risk_score}%</div>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <div className="text-gray-400">Threshold Used</div>
                  <div className="font-bold text-lg">{result.threshold_used}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}