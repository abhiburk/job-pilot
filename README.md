# 🚀 Job Pilot (Currently Building)

<p align="center">
  <b>Automated job discovery & personalized daily email digests delivered straight to your inbox.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/status-active-orange.svg" alt="Status">
</p>

---

## 📌 Overview

**Job Pilot** is an automated Python application designed to streamline your career search. It runs on a daily schedule, scanning multiple platforms for relevant openings matching your criteria, filtering out duplicates, and delivering a curated **daily job digest email** directly to your inbox so you never miss an opportunity.

---

## ✨ Key Features

-   **Daily Email Digests:** Receive automated daily email reports summarizing new, highly relevant job postings.
-   **Smart Deduplication:** Tracks delivered postings so you never receive duplicate listings in your inbox.
-   **Automated Job Scraping:** Continuously aggregates listings from major job boards and company career pages.
-   **Advanced Filtering:** Filters listings based on target keywords, remote/hybrid preferences, experience level, and salary ranges.
-   **Application & Digest Tracking:** Logs job postings, match scores, and digest delivery history in a relational database.

---

## 🛠️ Tech Stack

-   **Language:** Python 3.10+
-   **Database & ORM:** SQLAlchemy 2.0, PostgreSQL / SQLite
-   **Automation & Scraping:** Playwright / BeautifulSoup / Requests
-   **Notification & Email:** SMTP / Email APIs (SendGrid, Mailgun, or Gmail API)
-   **Scheduling:** Cron / APScheduler / Celery