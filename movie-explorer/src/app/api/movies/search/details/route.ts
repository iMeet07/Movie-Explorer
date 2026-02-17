import { NextResponse } from "next/server"

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const id = searchParams.get("id")

  if (!id) {
    return NextResponse.json({ error: "Missing id" }, { status: 400 })
  }

  try {
    const res = await fetch(
      `https://api.themoviedb.org/3/movie/${id}?api_key=${process.env.TMDB_API_KEY}`
    )

    if (!res.ok) {
      return NextResponse.json(
        { error: "Movie API unavailable" },
        { status: res.status }
      )
    }

    const data = await res.json()

    return NextResponse.json({
      id: data.id,
      title: data.title,
      overview: data.overview,
      poster_path: data.poster_path,
      release_date: data.release_date,
      runtime: data.runtime,
    })
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch details" },
      { status: 500 }
    )
  }
}
