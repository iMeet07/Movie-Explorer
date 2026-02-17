# Movie Explorer

A simple Movie Explorer web app built as a take-home project. Users can search movies, view details, and save favorites with personal ratings and notes.

## 🌐 Live Demo

movie-explorer-mu-sage.vercel.app

## 📦 Repository

https://github.com/iMeet07/Movie-Explorer

---

## ✨ Features

### 🔎 Search
- Search movies by title
- Results display:
  - Poster
  - Title
  - Release date
  - Short overview
- Debounced search input to reduce unnecessary API calls

### 🎬 Movie Details
- Details modal for selected movie
- Displays:
  - Poster
  - Full overview
  - Release date
  - Runtime (if available)
- Modal can be closed via:
  - Close button
  - Clicking outside
  - ESC key

### ⭐ Favorites
- Add / remove movies from favorites
- Prevents duplicate favorites
- Each favorite supports:
  - Personal rating (1–5)
  - Optional note

### 💾 Persistence
- Favorites stored in LocalStorage
- Data survives page refresh

### ⚠️ Error Handling
- Empty search state
- No results state
- API/network error handling
- Loading skeleton UI

---

## 🧱 Tech Stack

- Next.js (App Router)
- React
- TypeScript
- Tailwind CSS
- Next.js API Routes (server-side proxy)
- LocalStorage for persistence

---

## 🔐 API Integration

Movie data is fetched from TMDB via server-side API routes.

Flow:

Frontend → Next.js API Route → TMDB API

### Why this approach?
- Keeps API key secure (never exposed to browser)
- Centralized error handling
- Allows future response normalization/caching

---


---

## 🧠 Technical Decisions & Tradeoffs

### 1. API Proxy
Used Next.js API routes to hide the TMDB API key and decouple frontend from external APIs.

### 2. State Management
Used React local state + custom hooks instead of global state libraries to keep complexity low for the scope of the project.

### 3. Persistence
LocalStorage was chosen as the baseline persistence strategy to satisfy requirements quickly without adding backend complexity.

### 4. UI Approach
Focused on functionality and clarity over heavy styling, keeping the workflow straightforward.

---

## ⚖️ Known Limitations

- No pagination or infinite scrolling
- No server-side persistence/database
- Basic styling only
- No authentication or user accounts

---

## 🚀 Improvements With More Time

- Server-side favorites persistence
- Pagination or infinite scroll
- API response caching
- Accessibility improvements (ARIA labels, keyboard navigation)
- Better mobile responsiveness
- Unit/integration tests

---
