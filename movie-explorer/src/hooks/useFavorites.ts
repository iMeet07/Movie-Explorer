"use client"

import { useEffect, useState } from "react"
import { FavoriteMovie } from "@/types/movie"

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteMovie[]>([])

  useEffect(() => {
    const stored = localStorage.getItem("favorites")
    if (stored) setFavorites(JSON.parse(stored))
  }, [])

  useEffect(() => {
    localStorage.setItem("favorites", JSON.stringify(favorites))
  }, [favorites])

  const addFavorite = (movie: FavoriteMovie) => {
    setFavorites(prev =>
      prev.find(m => m.id === movie.id) ? prev : [...prev, movie]
    )
  }

  const removeFavorite = (id: number) => {
    setFavorites(prev => prev.filter(m => m.id !== id))
  }

  const updateFavorite = (id: number, data: Partial<FavoriteMovie>) => {
    setFavorites(prev =>
      prev.map(m => (m.id === id ? { ...m, ...data } : m))
    )
  }

  return { favorites, addFavorite, removeFavorite, updateFavorite }
}
