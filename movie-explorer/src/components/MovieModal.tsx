import { Movie } from "@/types/movie"
import { useEffect } from "react"

const IMG = "https://image.tmdb.org/t/p/w300"

type Props = {
  movie: Movie
  onClose: () => void
}

export default function MovieModal({ movie, onClose }: Props) {
  // Prevent background scrolling
  useEffect(() => {
    document.body.style.overflow = "hidden"

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }

    window.addEventListener("keydown", handleEsc)

    return () => {
      document.body.style.overflow = "auto"
      window.removeEventListener("keydown", handleEsc)
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-white text-black max-w-lg w-full rounded-xl p-6 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        {movie.poster_path && (
          <img
            src={`${IMG}${movie.poster_path}`}
            className="w-40 mb-4 rounded"
            alt={movie.title}
          />
        )}

        <h2 className="text-2xl font-bold mb-1">{movie.title}</h2>

        <p className="text-sm text-gray-600 mb-3">
          {movie.release_date} • {movie.runtime || "N/A"} min
        </p>

        <p className="text-gray-800 leading-relaxed">
          {movie.overview || "No description available."}
        </p>

        <button
          onClick={onClose}
          className="mt-5 bg-black text-white px-4 py-2 rounded hover:opacity-90"
        >
          Close
        </button>
      </div>
    </div>
  )
}
