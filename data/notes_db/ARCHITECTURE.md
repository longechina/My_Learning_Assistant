# Notes Database (notes_db/)

## Purpose
Stores all user notes and AI-generated real-time notes.

## Structure
- `associated/` : Notes linked to specific courses and chapters
- `independent/` : Notes not linked to any course
- `ai_realtime/` : AI-generated notes
- `notes_index.json` : Index for searching notes
- `NOTES_UPLOAD_RULES.md` : Rules for naming and uploading notes

## Features
- Supports multiple file types: `.md`, `.pdf`, `.docx`, `.xlsx`, images, audio, video
- UI validation on upload
- Linked to media_db, flashcard_db, courses_db for context-aware note management
