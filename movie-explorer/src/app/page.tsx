"use client"

import { useEffect, useState } from "react"
import { Movie } from "@/types/movie"
import { useFavorites } from "@/hooks/useFavorites"
import { useDebounce } from "@/hooks/useDebounce"

import SearchBar from "@/components/SearchBar"
import MovieCard from "@/components/MovieCard"
import MovieModal from "@/components/MovieModal"
import FavoritesPanel from "@/components/FavoritesPanel"

export default function Home() {
  const [query, setQuery] = useState("")
  const [movies, setMovies] = useState<Movie[]>([])
  const [selected, setSelected] = useState<Movie | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const debouncedQuery = useDebounce(query, 400)

  const { favorites, addFavorite, removeFavorite, updateFavorite } =
    useFavorites()

  const searchMovies = async (q: string) => {
    if (!q.trim()) {
      setMovies([])
      return
    }

    setLoading(true)
    setError("")

    try {
      const res = await fetch(`/api/movies/search?q=${q}`)

      if (!res.ok) throw new Error()

      const data = await res.json()
      setMovies(data)
    } catch {
      setError("Failed to search movies")
    }

    setLoading(false)
  }

  useEffect(() => {
    searchMovies(debouncedQuery)
  }, [debouncedQuery])

  const isFavorite = (id: number) =>
    favorites.some(f => f.id === id)

  return (
    <main className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Movie Explorer</h1>

      <SearchBar value={query} onChange={setQuery} />

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 bg-gray-100 animate-pulse rounded" />
          ))}
        </div>
      )}

      {!loading && query && movies.length === 0 && (
        <p>No results found.</p>
      )}

      <div className="grid md:grid-cols-3 gap-6 mt-4">
        <div className="md:col-span-2 space-y-4">
          {movies.map(movie => (
            <MovieCard
              key={movie.id}
              movie={movie}
              onDetails={() => setSelected(movie)}
              onFavorite={() =>
                isFavorite(movie.id)
                  ? removeFavorite(movie.id)
                  : addFavorite(movie)
              }
              isFavorite={isFavorite(movie.id)}
            />
          ))}
        </div>

        <FavoritesPanel
          favorites={favorites}
          updateFavorite={updateFavorite}
          removeFavorite={removeFavorite}
        />
      </div>

      {selected && (
        <MovieModal movie={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
