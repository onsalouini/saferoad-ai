import { useEffect } from "react"
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet"
import "leaflet/dist/leaflet.css"
import { STATUS, fmt } from "../lib/risk"

// Tuiles OpenStreetMap standard, assombries en CSS (.map-dark) pour le thème sombre
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
const ATTRIB = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

function FitBounds({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points.length >= 2) map.fitBounds(points, { padding: [40, 40] })
    else if (points.length === 1) map.setView(points[0], 11)
  }, [map, points])
  return null
}

function ClickHandler({ onClick }) {
  useMapEvents({ click: (e) => onClick?.(e.latlng) })
  return null
}

/** Découpe l'itinéraire en tronçons colorés selon le niveau de risque du point échantillonné. */
function coloredSegments(route) {
  const segs = route.segments
  const out = []
  for (let i = 0; i < segs.length; i++) {
    const from = i === 0 ? 0 : Math.round((segs[i - 1].geometry_index + segs[i].geometry_index) / 2)
    const to = i === segs.length - 1 ? route.geometry.length - 1
      : Math.round((segs[i].geometry_index + segs[i + 1].geometry_index) / 2)
    out.push({ positions: route.geometry.slice(from, to + 1), seg: segs[i] })
  }
  return out
}

export default function RouteMap({ origin, destination, routes = [], selected = 0, onSelect, onMapClick, height = 460 }) {
  const fitPoints = routes.length
    ? routes[selected].geometry
    : [origin, destination].filter(Boolean).map((p) => [p.lat, p.lng])

  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} scrollWheelZoom style={{ height }} className="w-full">
      <TileLayer url={TILES} attribution={ATTRIB} className="map-dark" maxZoom={19} />
      <FitBounds points={fitPoints} />
      <ClickHandler onClick={onMapClick} />

      {routes.map((r, i) => i !== selected && (
        <Polyline key={`alt-${i}`} positions={r.geometry} eventHandlers={{ click: () => onSelect?.(i) }}
          pathOptions={{ color: "#898781", weight: 5, opacity: 0.55 }}>
          <Tooltip sticky>Itinéraire {i + 1} · indice {fmt.num(r.summary.risk_score)} — cliquer pour afficher</Tooltip>
        </Polyline>
      ))}

      {routes[selected] && coloredSegments(routes[selected]).map(({ positions, seg }, i) => (
        <Polyline key={`seg-${i}`} positions={positions}
          pathOptions={{ color: STATUS[seg.status].hex, weight: 7, opacity: 0.95, lineCap: "round" }} />
      ))}

      {routes[selected]?.segments.map((s, i) => (
        <CircleMarker key={`pt-${i}`} center={[s.lat, s.lng]} radius={6}
          pathOptions={{ color: "#161b22", weight: 2, fillColor: STATUS[s.status].hex, fillOpacity: 1 }}>
          <Tooltip direction="top" offset={[0, -6]}>
            <div className="text-xs">
              <div className="font-semibold">Km {fmt.num(s.km, 0)} · {s.state || "hors USA"}</div>
              <div>Indice {fmt.num(s.risk_score)} · {STATUS[s.status].label}</div>
              <div>{s.weather.weather_label}, {fmt.fToC(s.weather.Temperature_F)} °C</div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}

      {origin && (
        <CircleMarker center={[origin.lat, origin.lng]} radius={9}
          pathOptions={{ color: "#f0efec", weight: 3, fillColor: "#3987e5", fillOpacity: 1 }}>
          <Tooltip permanent direction="top" offset={[0, -8]}>Départ</Tooltip>
        </CircleMarker>
      )}
      {destination && (
        <CircleMarker center={[destination.lat, destination.lng]} radius={9}
          pathOptions={{ color: "#f0efec", weight: 3, fillColor: "#f0efec", fillOpacity: 1 }}>
          <Tooltip permanent direction="top" offset={[0, -8]}>Arrivée</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  )
}
