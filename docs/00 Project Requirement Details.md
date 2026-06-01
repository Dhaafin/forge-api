# FORGE — Gym Tracker Platform

## Product Requirements Document — v2.0

---

## 1. Overview

Forge adalah platform gym tracker yang berjalan secara online. User mencatat latihan harian via aplikasi Android (Expo). Semua data tersimpan di cloud (Neon PostgreSQL) via FastAPI backend.

Sistem **invite-only** — user baru di-invite admin via email, lalu langsung bisa mulai tracking di mobile app. Tidak ada admin dashboard web — admin kelola user dan data langsung dari command line atau SQL.

---

## 2. System Architecture

|Layer|Teknologi|Fungsi|
|---|---|---|
|Mobile App (user)|Expo / React Native + NativeWind|Interface utama untuk log workout, lihat progress, terima notif, AI Coach|
|API Layer|FastAPI (Python)|REST API: auth, workout CRUD, notifikasi, AI Coach analysis|
|Database|Neon PostgreSQL (serverless)|Penyimpanan semua data user, workout, session|
|ORM|SQLAlchemy + Alembic|Type-safe query, migration database|
|Auth|FastAPI JWT (python-jose)|JWT token, invite system, role-based access|
|Push Notification|Expo Push Notification Service|Server-triggered notif ke device user|
|LLM AI Coach|Deepseek (via OpenRouter API)|Analisis workout, saran personal berbasis LLM|
|Hosting API|VPS (DigitalOcean / Vultr)|Deploy FastAPI dengan full control, cost-efficient|
|Hosting Database|Neon PostgreSQL (serverless)|Cloud database, tidak perlu manage server|
|Task Scheduler|APScheduler (in-process)|Cron job daily reminder notifikasi|
|Email|Resend API|Free tier 3000 email/bulan untuk invite system|

---

## 3. Problem Statement

- Mencatat workout manual (notes, spreadsheet) tidak efisien dan sering terlewat.
- Tidak ada sistem proaktif yang mengingatkan dan menyarankan progressive overload.
- Data workout tersimpan lokal — hilang kalau ganti HP, tidak bisa diakses dari mana saja.
- Tidak ada feedback cerdas berbasis data untuk membantu user berkembang lebih optimal.

---

## 4. Goals & Non-Goals

### Goals (MVP)

- User bisa login dengan akun yang di-invite oleh admin (via email invite).
- User mencatat sesi latihan: exercise, sets, reps, weight — tersimpan ke cloud.
- Sistem mengirim push notification harian jika user belum log workout.
- Sistem mendeteksi stagnasi dan menyarankan progressive overload.
- PR otomatis terdeteksi dan user mendapat alert saat PR baru tercapai.
- AI Coach memberikan analisis singkat setelah user selesai log workout (powered by Deepseek via OpenRouter).
- User bisa tambah exercise custom, edit, dan hapus (dengan protection untuk workout history).

### Non-Goals (di luar MVP)

- Tidak ada admin dashboard web — admin kelola via CLI atau langsung SQL.
- Tidak ada fitur sosial (follow, share workout, leaderboard) di MVP.
- Grafik progress dan body measurement tracker masuk V2.
- iOS support menyusul setelah Android stable.
- Tidak ada payment/subscription system di MVP.

---

## 5. User Roles & Permissions

|Role|Deskripsi|
|---|---|
|Admin|Developer/owner — manage user via CLI/SQL, kirim invite via script, lihat logs|
|User|Member biasa — log workout, terima notif, interact dengan AI Coach, kelola data pribadi|

---

## 6. Feature List

**Prioritas:** `P0` = MVP wajib · `P1` = segera setelah MVP · `P2` = V2

### Mobile App (User)

| Fitur                        | Deskripsi                                                                          | Prioritas |
| ---------------------------- | ---------------------------------------------------------------------------------- | --------- |
| Login dengan invite token    | User masukkan token dari email invite untuk aktivasi akun + set password           | P0        |
| Log Workout Harian           | Pilih exercise, tambah sets/reps/weight, simpan ke cloud via API                   | P0        |
| Exercise Library + Custom    | 13 gerakan bawaan + bisa tambah/edit/hapus exercise custom                         | P0        |
| PR Alert                     | Deteksi otomatis PR baru saat save set, tampil alert & simpan ke history           | P0        |
| Daily Push Notification      | Server kirim push notif jika belum ada log hari ini (jam bisa diset user)          | P0        |
| Progressive Overload Suggest | Setelah 3 sesi stagnasi per gerakan, API kirim saran naikkan weight/reps           | P0        |
| AI Coach Analysis            | Setelah log workout selesai, Deepseek generate analisis singkat dan saran personal | P0        |
| Workout History & CRUD       | Lihat semua sesi, filter per exercise/tanggal, edit/hapus sesi workout             | P1        |
| Streak & Dashboard           | Tampil streak harian dan statistik minggu ini di home screen                       | P1        |
| Progress Grafik              | Grafik weight/volume per exercise dari waktu ke waktu                              | P2        |
| Body Measurement Tracker     | Catat berat badan dan ukuran tubuh, simpan ke cloud                                | P2        |

---

## 7. Auth Flow

### Invite Flow

1. Admin buat invite via CLI script → sistem generate token unik (expire 7 hari).
2. Email dikirim ke calon user berisi link aktivasi: `https://app.forge.local/invite?token=xxx`
3. User buka link di mobile app, isi nama + password, akun aktif dan langsung bisa login.
4. Token single-use: setelah dipakai, tidak bisa dipakai lagi.

### Session Management

- FastAPI JWT auth menggunakan python-jose + native bcrypt.
- Access token expire 15 menit, refresh token 30 hari.
- Mobile app simpan token di SecureStore (Expo).
- Role check di setiap protected endpoint via FastAPI dependency injection.

---

## 8. Key API Endpoints

|Method|Endpoint|Fungsi|
|---|---|---|
|POST|`/api/v1/auth/activate`|Aktivasi akun via invite token|
|POST|`/api/v1/auth/login`|Login, return JWT access + refresh token|
|POST|`/api/v1/auth/refresh`|Refresh access token|
|GET|`/api/v1/workouts`|Ambil semua workout session milik user|
|POST|`/api/v1/workouts`|Buat workout session baru|
|PUT|`/api/v1/workouts/{id}`|Edit workout session|
|DELETE|`/api/v1/workouts/{id}`|Hapus workout session|
|POST|`/api/v1/workouts/{id}/sets`|Tambah set ke workout session|
|GET|`/api/v1/exercises`|Ambil exercise library (bawaan + custom)|
|POST|`/api/v1/exercises`|Tambah exercise custom baru|
|PUT|`/api/v1/exercises/{id}`|Edit exercise custom|
|DELETE|`/api/v1/exercises/{id}`|Hapus exercise custom (with RESTRICT protection)|
|GET|`/api/v1/pr`|Ambil semua PR milik user|
|GET|`/api/v1/suggest`|Ambil progressive overload suggestions|
|POST|`/api/v1/ai/coach`|Generate AI Coach analysis setelah workout selesai|
|POST|`/api/v1/notifications/register`|Daftarkan Expo push token user|
|GET|`/api/v1/notifications/history`|Ambil history notifikasi user|

---

## 9. User Stories

### User (Mobile)

|ID|User Story|Acceptance Criteria|
|---|---|---|
|US-01|Sebagai user baru, saya ingin mengaktifkan akun saya via link invite.|Token divalidasi, expire >7 hari ditolak; akun aktif setelah submit; redirect ke login|
|US-02|Sebagai user, saya ingin login ke app dengan email dan password.|Login dapat JWT; token di SecureStore; salah password ada error; auto-login jika token valid|
|US-03|Sebagai user, saya ingin mencatat sesi workout hari ini.|Pilih exercise; tambah sets/reps/weight; data ter-save ke cloud; tampil konfirmasi|
|US-04|Sebagai user, saya ingin dapat notifikasi jika belum log workout hari ini.|Notif muncul di jam terkonfigurasi; tidak muncul kalau sudah ada log; tap notif buka log screen|
|US-05|Sebagai user, saya ingin tahu kalau saya memecahkan PR.|Alert muncul saat set melampaui PR; tampil exercise dan nilai PR baru; PR tersimpan|
|US-06|Sebagai user, saya ingin mendapat saran naikkan beban setelah stagnasi.|Saran muncul setelah 3 sesi stagnasi per gerakan; spesifik exercise dan rekomendasi; bisa dismiss|
|US-07|Sebagai user, saya ingin mendapat analisis dari AI Coach setelah selesai workout.|AI Coach generate summary: volume, highlight PR, satu saran personal; muncul di akhir sesi|
|US-08|Sebagai user, saya ingin tambah exercise custom yang tidak ada di daftar bawaan.|Form sederhana: nama + kategori + muscle group; exercise tersimpan dan bisa dipakai di sesi berikutnya|
|US-09|Sebagai user, saya ingin edit atau hapus sesi workout yang sudah tercatat.|Bisa klik sesi → edit beban/reps/durasi; atau hapus sesi penuh dari history|

---

## 10. Tech Stack

|Layer|Teknologi|Alasan|
|---|---|---|
|Mobile Framework|Expo (React Native)|Familiar dengan React, build Android tanpa config native|
|Mobile Styling|NativeWind (Tailwind)|Syntax Tailwind yang sudah dikuasai|
|Mobile State|React Context + Hooks|Native React state management, tidak perlu library eksternal|
|API Framework|FastAPI (Python)|Modern, async, type-safe, ekosistem AI/ML terbaik|
|ORM|SQLAlchemy + Alembic|Industry standard Python ORM + migration tool|
|Database|Neon PostgreSQL (serverless)|Free tier generous, serverless, tidak perlu manage server|
|Auth|python-jose + native bcrypt|JWT standard untuk FastAPI, bcrypt password hashing native (Python 3.12+)|
|LLM|Deepseek via OpenRouter API|Cost-efficient LLM untuk analisis workout, competitive dengan ChatGPT|
|Push Notif|Expo Push Notification Service|Free, terintegrasi langsung dengan Expo app|
|Scheduler|APScheduler|In-process cron job (daemon thread) untuk daily notification|
|Email|Resend API|Free tier 3000 email/bulan untuk kirim invite|
|Hosting API|VPS (DigitalOcean/Vultr)|Full control, cost-efficient (~$5-10/month), learning experience backend production|
|HTTP Client|httpx|Async HTTP client untuk call OpenRouter API|

---

## 11. Business Logic & Implementation Details

### M1: Database Core & Launchpad System

**Perubahan Skema Tipe Data ID**

- Primary Key untuk tabel `users` menggunakan UUID v4 (bukan Integer serial) untuk standar keamanan industri tinggi dan anti-scraping protection.

**Penyelarasan Format URL (.env)**

- Connection String pada `.env` Windows **wajib** menggunakan driver modern `postgresql://` (bukan `postgres://`) untuk mencegah kegagalan inisialisasi Alembic Migration Engine.

### M2: Authentication & Closed Security System

**Pembatasan Registrasi Publik**

- Tidak ada self-registration. Semua user baru wajib melewati gerbang Invite Token tunggal dari Admin.
- Token kedaluwarsa otomatis dalam 7 hari dan single-use (tidak bisa dipake dua kali).

**Native Bcrypt Implementation**

- Menghapus ketergantungan pada `passlib[bcrypt]` yang memiliki limitasi 72-bytes bug pada Python 3.12+.
- Menggunakan native `bcrypt` library langsung untuk password hashing.

**OAuth2 Form-Data Standardisasi**

- Endpoint `POST /api/v1/auth/login` menerima format `application/x-www-form-data` (bukan JSON).
- Field: `username` dan `password` agar kompatibel dengan OpenAPI Swagger Docs authorization button.

### M3: Workouts Core Business Logic

**Pencabangan Relasional Tabel**

- Skema relasi database terpusat pada 3 tabel: `exercises` (master gerakan), `workout_sessions` (tanggal & durasi), `workout_sets` (beban kg & reps).

**Relasi ForeignKey Terproteksi**

- Foreign key `exercise_id` di tabel `workout_sets` menggunakan constraint `ondelete="RESTRICT"`.
- User/admin **tidak bisa menghapus exercise** jika sudah digunakan di workout history — demi menjaga integritas sejarah angkatan.

### M5: Proactive Reminder & Analytics Engine

**Otomatisasi Cron Latar Belakang**

- APScheduler berjalan sebagai daemon thread di lifespan startup/shutdown FastAPI.
- Deteksi user pasif (bolos 3 hari) setiap 24 jam secara otomatis.

**Refactor Logika Progressive Overload**

- Dari evaluasi Volume Sesi Global (yang menyebabkan bug deteksi multi-exercise sesi), diubah menjadi **Analisis Granular Per Gerakan Spesifik** (`exercise_id`).
- Sistem mendeteksi peningkatan volume angkatan per gerakan, tidak tercampur dengan jenis otot lain.

### M6: Complete Workout & Exercise Lifecycle (CRUD Global)

**Konsolidasi Fungsionalitas Member & Admin**

- Seluruh operasi manipulasi data (workout history, exercise custom) digabung ke dalam Mobile App.
- Member bisa langsung tambah/edit/hapus exercise dan sesi workout dari HP mereka.

**Endpoint Mutasi Sesi Latihan**

- `GET /api/v1/workouts` → Tarik seluruh garis waktu sejarah latihan user
- `PUT /api/v1/workouts/{id}` → Koreksi kesalahan ketik (beban/durasi) pasca-latihan
- `DELETE /api/v1/workouts/{id}` → Hapus catatan satu sesi latihan dari database cloud

**Endpoint Modifikasi Gerakan (Exercise CRUD)**

- `POST /api/v1/exercises` → Tambah gerakan custom baru dari 13 gerakan dasar bawaan
- `PUT /api/v1/exercises/{id}` → Edit nama gerakan custom lokal
- `DELETE /api/v1/exercises/{id}` → Hapus gerakan master lokal (Dilindungi RESTRICT constraint agar riwayat set lama tidak terhapus)

### M6.5: AI Coach Integration dengan Deepseek

**OpenRouter API Integration**

- Endpoint `POST /api/v1/ai/coach` memanggil Deepseek via OpenRouter API.
- Prompt engineering spesifik untuk gym context: analisis volume, PR highlight, saran progressive overload.

**Cost Optimization**

- Deepseek jauh lebih murah daripada GPT-4 (~$0.003 per 1K input tokens).
- Batch request AI Coach jika user banyak, jangan call per user secara real-time.

---

## 12. Database Schema Overview

|Tabel|Kolom Utama|Relasi|
|---|---|---|
|`users`|id (UUID), name, email, password_hash, role, is_active, created_at|—|
|`invite_tokens`|id, token, email, role, invited_by, used_at, expires_at|invited_by → users.id|
|`exercises`|id, name, category, muscle_group, is_custom, created_by, created_at|created_by → users.id|
|`workout_sessions`|id, user_id, date, notes, duration_minutes, created_at|user_id → users.id|
|`workout_sets`|id, session_id, exercise_id, reps, weight_kg, set_number, created_at|session_id → sessions, exercise_id → exercises (RESTRICT)|
|`personal_records`|id, user_id, exercise_id, weight_kg, reps, achieved_at|user_id, exercise_id → users, exercises|
|`push_tokens`|id, user_id, expo_token, created_at|user_id → users.id|
|`notifications`|id, user_id, type, message, sent_at, read_at|user_id → users.id|
|`ai_coach_logs`|id, user_id, session_id, prompt, response, tokens_used, created_at|user_id, session_id → users, sessions|

---

## 13. FastAPI Project Structure

```
forge-api/
  app/
    main.py                    # FastAPI app entry point + lifespan
    config.py                  # Settings, env vars, constants
    database.py                # SQLAlchemy engine & session
    dependencies.py            # Shared FastAPI dependencies (auth, db)
    models/                    # SQLAlchemy ORM models
      user.py
      workout.py
      exercise.py
      invite_token.py
      personal_record.py
    schemas/                   # Pydantic schemas (request/response)
      user.py
      workout.py
      exercise.py
      ai_coach.py
    routers/                   # Route handlers per domain
      auth.py                  # login, refresh, activate invite
      workouts.py              # CRUD workout sessions & sets
      exercises.py             # CRUD exercises
      ai_coach.py              # POST /ai/coach
      notifications.py         # register, history
    services/                  # Business logic layer
      workout_service.py       # PR detection, progressive overload logic
      ai_service.py            # OpenRouter API calls, prompt engineering
      notification_service.py  # push notification logic
      auth_service.py          # invite token generation, password hashing
    scheduler/                 # APScheduler cron jobs
      daily_reminder.py        # daily notification job
      passive_user_detector.py # detect inactive users
    utils/                     # Helper functions
      email.py                 # send invite email via Resend
      jwt.py                   # JWT encode/decode
      deepseek.py              # Deepseek API wrapper
  alembic/                     # Database migrations
    versions/
  tests/
  requirements.txt
  .env.example
  docker-compose.yml           # optional: untuk local dev
  Dockerfile                   # untuk VPS deployment
```

---

## 14. VPS Deployment Notes

### Recommended VPS Setup

- **Provider**: DigitalOcean (Ubuntu 22.04) / Vultr ($6-10/month)
- **Python**: 3.12+
- **Process Manager**: systemd service
- **Reverse Proxy**: Nginx
- **SSL**: Let's Encrypt (free)
- **Monitoring**: Simple status check via cron

### Minimal Deployment Steps

1. Clone repo → `cd forge-api`
2. Create virtual env → `python -m venv venv`
3. Install deps → `pip install -r requirements.txt`
4. Setup .env dengan Neon DB URL, OpenRouter API key, Resend API key
5. Run migrations → `alembic upgrade head`
6. Start FastAPI → `uvicorn app.main:app --host 0.0.0.0 --port 8000`
7. Reverse proxy via Nginx ke localhost:8000

---

## 15. Constraints & Assumptions

### Constraints

- Semua fitur butuh koneksi internet — tidak ada offline mode.
- Email service dibatasi free tier Resend: 3.000 email/bulan.
- Neon PostgreSQL free tier: 0.5 GB storage, 190 compute hours/bulan.
- Deepseek via OpenRouter: bayar per token (~$0.003 per 1K input).
- VPS cost: ~$5-10/month untuk production-grade backend.
- Solo developer — scope MVP harus bisa diselesaikan sendiri.

### Assumptions

- Jumlah user awal kecil (<50), tidak butuh horizontal scaling di MVP.
- Admin adalah developer itu sendiri — manage user via CLI atau langsung SQL.
- Progressive overload threshold: 3 sesi berturut-turut dengan weight dan reps sama per exercise spesifik.
- AI Coach dipanggil hanya saat user selesai dan submit satu sesi workout penuh.
- User memiliki koneksi internet yang stabil saat menggunakan app.

---

## 16. Milestones

|Milestone|Deliverable|Scope|
|---|---|---|
|M1|Project Setup|Repo setup, Neon DB, SQLAlchemy schema & Alembic, VPS provisioning|
|M2|Auth System (FastAPI)|FastAPI JWT auth, invite flow, email via Resend, aktivasi akun, login endpoint|
|M3|Core API (FastAPI)|CRUD workout sessions & sets, exercise library + custom, PR detection logic|
|M4|Mobile App — Core|Log workout UI, exercise picker, PR alert, connect ke FastAPI endpoints|
|M5|Proactive Engine|Push notif registration, APScheduler daily reminder, progressive overload detector|
|M6|AI Coach Integration|Deepseek via OpenRouter, endpoint /api/v1/ai/coach, prompt engineering, tampil di mobile|
|M7|Complete CRUD|Edit/delete workout sessions, add/edit/delete exercise custom dengan RESTRICT protection|
|M8|Polish & Testing|Error handling, loading states, edge cases, VPS deployment testing|
|M9|MVP Release|Build APK via EAS, deploy ke VPS, internal testing, go live|

---

## 17. V2 Roadmap

- Progress grafik per exercise (weight/volume over time).
- Body measurement tracker dengan grafik.
- AI Coach yang lebih canggih: analisis tren mingguan, injury prevention tips, personalized program.
- iOS support (EAS Build).
- Offline mode dengan sync saat online kembali.
- Export data workout ke CSV/PDF.
- Leaderboard dan social features.
- Payment/subscription jika di-monetize.

---

_Forge PRD v2.0 — Living document, update seiring development._