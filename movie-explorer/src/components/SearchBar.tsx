type Props = {
  value: string
  onChange: (v: string) => void
}

export default function SearchBar({ value, onChange }: Props) {
  return (
    <div className="mb-6">
      <input
        className="w-full border rounded px-3 py-2"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="Search movies..."
      />
    </div>
  )
}
