import { NextResponse } from "next/server"

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const q = searchParams.get("q")

  if (!q) {
    return NextResponse.json({ error: "Missing query" }, { status: 400 })
  }

  try {
    const res = await fetch(
      `https://api.themoviedb.org/3/search/movie?api_key=${process.env.TMDB_API_KEY}&query=${encodeURIComponent(q)}`
    )

    if (!res.ok) {
      return NextResponse.json(
        { error: "Movie API unavailable" },
        { status: res.status }
      )
    }

    const data = await res.json()

    // normalize response (senior upgrade)
    const movies = (data.results || []).map((m: any) => ({
      id: m.id,
      title: m.title,
      overview: m.overview,
      poster_path: m.poster_path,
      release_date: m.release_date,
    }))

    return NextResponse.json(movies)
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch movies" },
      { status: 500 }
    )
  }
}
