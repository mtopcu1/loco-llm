export function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded border border-red-300 bg-red-50 p-4">
      <h3 className="font-medium text-red-800">{title}</h3>
      <p className="text-sm text-red-700">{message}</p>
    </div>
  )
}
