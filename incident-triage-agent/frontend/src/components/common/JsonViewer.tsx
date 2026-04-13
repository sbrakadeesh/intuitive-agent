export function JsonViewer({ data }: { data: unknown }) {
  return (
    <pre className="bg-gray-900 border border-gray-700 rounded p-3 text-xs text-gray-300 font-mono max-h-48 overflow-y-auto whitespace-pre-wrap break-all">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
