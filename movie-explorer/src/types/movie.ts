export type Movie = {
  id: number
  title: string
  overview: string
  poster_path: string | null
  release_date: string
  runtime?: number
}

export type FavoriteMovie = {
  id: number
  title: string
  poster_path: string | null
  rating?: number
  note?: string
}
