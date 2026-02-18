import React, { useEffect, useState } from 'react'

export default function Digests() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [previewUrl, setPreviewUrl] = useState(null)

  useEffect(() => {
    fetch('/api/digests')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const digests = data?.digests || []

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Digest History</h2>

      {previewUrl && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-vpg-navy">Preview</h3>
            <button
              onClick={() => setPreviewUrl(null)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Close Preview
            </button>
          </div>
          <iframe
            src={previewUrl}
            className="w-full border rounded-lg shadow-sm bg-white"
            style={{ height: '700px' }}
            title="Digest Preview"
          />
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Filename</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Generated</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Size</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {digests.map(d => (
              <tr key={d.filename} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{d.filename}</td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {new Date(d.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">{d.size_kb} KB</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setPreviewUrl(d.preview_url)}
                    className="text-xs text-vpg-blue hover:underline mr-3"
                  >
                    Preview
                  </button>
                  <a
                    href={d.preview_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-gray-500 hover:underline"
                  >
                    Open in New Tab
                  </a>
                </td>
              </tr>
            ))}
            {digests.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                  No digests generated yet. Run the pipeline to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
