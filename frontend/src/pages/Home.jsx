import { Link } from "react-router-dom"

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[90vh] text-center px-4">
      <h1 className="text-5xl font-bold mb-4">
        Predict Road Risk <span className="text-blue-400">Before You Drive</span>
      </h1>
      <p className="text-gray-400 text-lg max-w-xl mb-8">
        SafeRoad AI analyzes weather, traffic, road conditions and historical 
        accidents to calculate your trip's risk score in real time.
      </p>
      <div className="flex gap-4 mb-12">
        <Link to="/predict"
          className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-xl text-lg font-semibold transition">
          Analyze My Trip →
        </Link>
      </div>
      <div className="grid grid-cols-3 gap-8 text-center mt-4">
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800">
          <div className="text-3xl font-bold text-blue-400">7.7M+</div>
          <div className="text-gray-400 mt-1">Accidents analyzed</div>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800">
          <div className="text-3xl font-bold text-blue-400">89.5%</div>
          <div className="text-gray-400 mt-1">ROC-AUC Score</div>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800">
          <div className="text-3xl font-bold text-blue-400">3 Modes</div>
          <div className="text-gray-400 mt-1">Standard / Pro / Strict</div>
        </div>
      </div>
    </div>
  )
}