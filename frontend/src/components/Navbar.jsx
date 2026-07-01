import { Link } from "react-router-dom"

export default function Navbar() {
  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🛣️</span>
        <span className="text-xl font-bold text-blue-400">SafeRoad AI</span>
      </div>
      <div className="flex gap-6">
        <Link to="/" className="text-gray-300 hover:text-white transition">Home</Link>
        <Link to="/predict" className="bg-blue-600 hover:bg-blue-500 px-4 py-1.5 rounded-lg transition">
          Predict Risk
        </Link>
      </div>
    </nav>
  )
}