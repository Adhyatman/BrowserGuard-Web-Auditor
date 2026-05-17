# 🌐 Web Crawler & AI-Based Website Analysis System

A full-stack web application that audits websites for structural issues, broken resources, and code quality problems using a **multi-threaded crawler** and **AI-powered insights**.

---

## 🚀 Overview

This system scans a website, analyzes its structure and resources, and generates actionable insights. It combines:

* **Breadth-First Search (BFS) crawling**
* **Multi-threaded execution**
* **Headless browser rendering (for JS-heavy sites)**
* **AI-based analysis using LLaMA models**

The application is fully asynchronous and uses a **job-based architecture**, allowing long-running scans without blocking the user interface.

---

## ✨ Key Features

### 🔍 Website Crawling

* BFS-based traversal for structured coverage
* Multi-threaded crawling using `ThreadPoolExecutor`
* Depth-limited scanning (up to 8 levels)
* Duplicate URL prevention

### ⚙️ Issue Detection

* Broken link detection (404, 500, etc.)
* Inline CSS detection (`style=""`)
* Commented code detection (HTML & JS)
* CSS & JavaScript resource analysis

### 🌍 Smart Crawling Enhancements

* Sitemap (`/sitemap.xml`) integration
* Robots.txt compliance
* Rate limiting to avoid blocking

### 🤖 AI-Powered Insights

* On-demand analysis using LLaMA 3 model via Groq API
* Issue prioritization and root cause analysis
* Optimization recommendations
* Cached AI responses per job

### 📊 Frontend Dashboard

* URL input and scan control
* Real-time job tracking (polling)
* Visual reports (charts, tables)
* AI insights view
* Downloadable results

---

## 🧱 Tech Stack

### Frontend

* React (Vite)
* Axios

### Backend

* Python + FastAPI
* Playwright (headless Chromium)
* ThreadPoolExecutor (concurrency)

### AI Integration

* Groq API (LLaMA 3.3 70B)

---

## ⚙️ Setup Guide

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd <project-folder>
```

---

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

* Runs on: **[http://localhost:5173](http://localhost:5173)**

---

### 3. Backend Setup

```bash
cd backend
python -m venv venv
```

#### Activate Virtual Environment

* Linux / Mac:

```bash
source venv/bin/activate
```

* Windows:

```bash
venv\Scripts\activate
```

---

### 4. Select Python Interpreter (VS Code)

If using Visual Studio Code:

* Press **Ctrl + Shift + P**
* Search: **Python: Select Interpreter**
* Choose the interpreter inside:

  ```
  backend/venv
  ```

---

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 6. Install Playwright (Required for JS Rendering)

```bash
playwright install
```

---

### 7. Run Backend Server

```bash
uvicorn main:app --reload
```

* Runs on: **[http://localhost:8000](http://localhost:8000)**

---

## 🔌 API Endpoints

* `POST /scan` → Run synchronous scan
* `POST /analyze` → Start async crawl job
* `GET /job/{job_id}` → Check status & results
* `POST /job/{job_id}/ai` → Generate AI insights
* `POST /stop` → Stop running crawl

---

## 🔄 Workflow

1. User enters a URL in frontend
2. Request sent to `/analyze`
3. Backend returns `job_id` immediately
4. Crawling runs in background
5. Frontend polls `/job/{job_id}`
6. Results displayed after completion
7. User can trigger AI insights

---

## 🧠 System Design Highlights

* Asynchronous job-based architecture
* Hybrid model: BFS (sequential) + threads (parallel)
* Modular detection pipeline
* Headless browser for dynamic content
* Stateless system (no database)

---

## ⚠️ Limitations

* No persistent storage (data lost on refresh)
* Depth-limited crawling (8 levels)
* AI responses are non-deterministic
* Performance depends on network and thread settings

---

## 🚀 Future Improvements

* Add database for result persistence
* Structured AI outputs (JSON format)
* Incremental crawling
* Authentication & user history
* Advanced filtering and reporting

---

## 📁 Backend Structure (Quick View)

* `crawler.py` → Core BFS crawler engine
* `routes.py` → API endpoints
* `ai_analyzer.py` → AI insights generation
* `html_fetcher.py` → Playwright-based rendering
* `link_extractor.py` → URL extraction
* `css_crawler.py` / `js_crawler.py` → Resource analysis
* `robots.py` / `sitemap.py` → Crawling rules & discovery
* `inline_detector.py` / `comment_detector.py` → Code quality checks

---
