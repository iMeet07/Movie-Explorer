import { FavoriteMovie } from "@/types/movie"

type Props = {
  favorites: FavoriteMovie[]
  updateFavorite: (id: number, data: Partial<FavoriteMovie>) => void
  removeFavorite: (id: number) => void
}

export default function FavoritesPanel({
  favorites,
  updateFavorite,
  removeFavorite,
}: Props) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Favorites</h2>

      {favorites.length === 0 && (
        <p className="text-sm text-gray-500">No favorites yet.</p>
      )}

      {favorites.map(f => (
        <div key={f.id} className="border rounded p-3 mb-3">
          <h3 className="font-medium">{f.title}</h3>

          <select
            className="border mt-2 px-2 py-1 rounded"
            value={f.rating || ""}
            onChange={e =>
              updateFavorite(f.id, { rating: Number(e.target.value) })
            }
          >
            <option value="">Rating</option>
            {[1, 2, 3, 4, 5].map(n => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>

          <textarea
            className="border w-full mt-2 p-2 rounded"
            placeholder="Note..."
            value={f.note || ""}
            onChange={e => updateFavorite(f.id, { note: e.target.value })}
          />

          <button
            onClick={() => removeFavorite(f.id)}
            className="mt-2 text-red-600 text-sm"
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  )
}
