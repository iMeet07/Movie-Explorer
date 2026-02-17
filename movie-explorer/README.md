# 🎬 Movie Explorer

A full-stack Movie Explorer web application built as a take-home assignment.  
Users can search for movies, view details, and save favorites with personal ratings and notes.

---

## 🌐 Live Demo

🔗 https://movie-explorer-mu-sage.vercel.app/

## 📦 Repository

🔗 https://github.com/iMeet07/Movie-Explorer

---

## ✨ Features

### 🔎 Movie Search
- Search movies by title
- Debounced input to reduce unnecessary API calls
- Results include:
  - Poster
  - Title
  - Release date
  - Short overview

### 🎬 Movie Details
- Modal-based details view
- Displays:
  - Poster
  - Full overview
  - Release date
  - Runtime (when available)
- Modal closes via:
  - Close button
  - Outside click
  - Escape key

### ⭐ Favorites
- Add or remove favorites
- Prevents duplicates
- Supports:
  - Personal rating (1–5)
  - Optional notes

### 💾 Persistence
- Favorites stored in LocalStorage
- Data survives browser refresh

### ⚠️ Error & Empty States
- Loading skeleton UI
- No results state
- API/network error handling

---

## 🧱 Tech Stack

- **Next.js (App Router)**
- **React**
- **TypeScript**
- **Tailwind CSS**
- **Next.js API Routes** (server-side proxy)
- **LocalStorage** for persistence

---

## 🔐 API Integration

Movie data is fetched from TMDB using server-side API routes.

**Request flow:**


### Why this approach?
- Keeps API key secure (never exposed to browser)
- Centralized API error handling
- Decouples frontend from third-party API structure
- Allows future caching/transformations

---

## 🧠 Technical Decisions & Tradeoffs

### 1️⃣ API Proxy
Used Next.js API routes to keep API credentials server-side and simplify frontend data fetching.

### 2️⃣ State Management
Used React local state and custom hooks instead of global state libraries to keep complexity low for project scope.

### 3️⃣ Persistence
LocalStorage was chosen for baseline persistence to satisfy requirements quickly without introducing backend infrastructure.

### 4️⃣ UI Approach
Prioritized core functionality and clear workflows over heavy styling due to time constraints.

---

## ⚖️ Known Limitations

- No pagination or infinite scrolling
- No server-side persistence/database
- Minimal styling focus
- No authentication or user accounts

---

## 🚀 Improvements With More Time

- Server-side persistence for favorites
- Pagination / infinite scrolling
- API response caching
- Accessibility enhancements
- Better mobile optimization
- Unit and integration tests

---

## ⚡ Setup in 5 Quick Steps

Get the project running locally in just a few minutes.

### 1️⃣ Clone the Repository

git clone https://github.com/iMeet07/Movie-Explorer.git
cd Movie-Explorer/movie-explorer

2️⃣ Install Dependencies

npm install

3️⃣ Configure Environment Variables

Create a .env.local file in the root directory:

TMDB_API_KEY=YOUR_TMDB_API_KEY
Get your free API key from The Movie Database (TMDB).

4️⃣ Start the Development Server

npm run dev
Open your browser and visit:

http://localhost:3000

MIT License
© 2026 Meet. All rights reserved.
