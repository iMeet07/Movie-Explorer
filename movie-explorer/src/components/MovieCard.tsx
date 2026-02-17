import { Movie } from "@/types/movie"

const IMG = "https://image.tmdb.org/t/p/w200"

type Props = {
  movie: Movie
  onDetails: () => void
  onFavorite: () => void
  isFavorite: boolean
}

export default function MovieCard({
  movie,
  onDetails,
  onFavorite,
  isFavorite,
}: Props) {
  return (
    <div className="border rounded p-4 flex gap-4">
      {movie.poster_path && (
        <img src={`${IMG}${movie.poster_path}`} className="w-24 rounded" />
      )}

      <div>
        <h3 className="font-semibold">{movie.title}</h3>
        <p className="text-sm text-gray-500">{movie.release_date}</p>
        <p className="text-sm mt-2 line-clamp-3">{movie.overview}</p>

        <div className="mt-3 flex gap-2">
          <button onClick={onDetails} className="border px-3 py-1 rounded">
            Details
          </button>
          <button
            onClick={onFavorite}
            className="bg-blue-600 text-white px-3 py-1 rounded"
          >
            {isFavorite ? "Remove" : "Favorite"}
          </button>
        </div>
      </div>
    </div>
  )
}
