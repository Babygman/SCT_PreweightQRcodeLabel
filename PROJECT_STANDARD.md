# PROJECT_STANDARD.md

Version: 2.0
Last Updated: 2026-08-05

# Core Principles

1. Business Goal มาก่อน Technology
2. ออกแบบก่อน Coding
3. ทำทีละ Phase และรออนุมัติก่อนเริ่มขั้นถัดไป
4. UAT คือแหล่งค้นหาความจริง ไม่ใช่ Unit Test
5. ChatGPT ออกแบบ สถาปัตยกรรม เขียน Prompt และ Review
6. Codex พัฒนาโค้ด ทดสอบ และ Commit
7. Push เมื่อ UAT ผ่านและ Working Tree เป็น Clean เท่านั้น
8. ทุก Feature ต้องตอบ Business Requirement
9. หลีกเลี่ยง Scope Creep
10. Simple is Better than Perfect

---

# 1. บทบาท

## Product Owner
- กำหนด Business Goal
- กำหนด Requirement
- ทำ UAT
- อนุมัติ Release
- จัดลำดับความสำคัญของงาน

## ChatGPT
- Technical Architect
- System Analyst
- Project Manager
- QA Reviewer
- Security Reviewer
- Performance Reviewer

หน้าที่:
- วิเคราะห์ Requirement
- ออกแบบ Architecture
- ออกแบบ Database
- ออกแบบ Workflow
- ออกแบบ UI/UX
- เขียน Prompt ให้ Codex
- Review งานและผล UAT
- ตัดสินใจ Approved / Not Approved

## Codex
หน้าที่:
- Coding
- Refactoring
- Bug Fix
- Migration
- Tests
- Documentation
- Git Commit

---

# 2. Workflow

Requirement
→ Architecture
→ Database
→ Workflow/UI
→ Approval
→ Prompt for Codex
→ Development
→ Commit
→ Run
→ UAT
→ Review
→ Fix (ถ้ามี)
→ Push
→ Merge
→ Release

---

# 3. Project Kickoff

ก่อน Coding ต้องทำ

1. Requirement Analysis
2. Business Goal
3. Scope
4. Risk Assessment
5. Architecture
6. Database Design
7. Workflow
8. UI/UX
9. Roadmap
10. รออนุมัติ

---

# 4. Git Standard

Branch:
- main
- feature/*
- hotfix/*

Push เมื่อ
- UAT ผ่าน
- Tests ผ่าน
- Working Tree Clean
- ChatGPT Approved

---

# 5. Database

- ใช้ Alembic Migration
- ห้ามแก้ Production Schema ตรง
- ทดสอบ Upgrade → Downgrade → Upgrade

---

# 6. Testing

ทุกครั้งต้องรัน
- Pytest
- Ruff
- Template Compile
- SQL Smoke Test (ถ้ามี)
- Manual UAT

---

# 7. UAT

Product Owner:
- ทดสอบจริง
- ส่ง Screenshot
- ส่ง Comment

ChatGPT:
- จัดประเภท Bug / Improvement / Expected / Question
- เขียน Prompt ให้ Codex

Codex:
- แก้เฉพาะงานที่ได้รับอนุมัติ

---

# 8. Security Checklist

ตรวจอย่างน้อย
- SQL Injection
- XSS
- CSRF
- Authentication
- Authorization
- Secret Management

---

# 9. Performance

ตรวจ
- Dashboard
- API
- SQL Query

ห้ามเกิด Performance Regression

---

# 10. Documentation

อัปเดตทุก Sprint
- README.md
- RELEASE.md
- CHANGELOG.md (ถ้ามี)
- เอกสารที่เกี่ยวข้อง

---

# 11. Environment Rule

ทุกคำสั่งต้องระบุ
- เครื่อง
- IDE
- Terminal
- Database
- Git Branch

---

# 12. Definition of Done

ถือว่าเสร็จเมื่อ
- UAT ผ่าน
- Tests ผ่าน
- Documentation ครบ
- Push สำเร็จ
- Working Tree Clean

---

# 13. Lessons Learned

เมื่อจบ Project ให้สรุป
- สิ่งที่ทำได้ดี
- สิ่งที่ต้องปรับปรุง
- Roadmap Version ถัดไป

---

# 14. Project Kickoff Template

Project Name:

Business Goal:

Objectives:

Target Users:

Technology Stack:

Operating System:

Programming Language:

Database:

Source Control:

Coding Tool:

AI Coding Tool:

Deployment:

Timeline:

Out of Scope:

Success Criteria:

## Development and Deployment Work Location

| งาน                                     | ทำที่ไหน                           |
| --------------------------------------- | ---------------------------------- |
| เขียน/แก้ Code                          | Codex บน MacBook Air               |
| Git / Commit / Push                     | Codex + GitHub                     |
| Automated Test / pytest / Ruff          | MacBook Air / Codex                |
| รัน Flask ระหว่าง Development           | MacBook Air → VS Code Terminal     |
| เปิดเว็บเพื่อทดสอบ                      | MacBook Air → Browser              |
| Database                                | `WEBSERVER01`                      |
| Migration / Seed ที่กระทบ Database จริง | เชื่อมไป Database บน `WEBSERVER01` |
| Production Deployment                   | `WEBSERVER01` เฉพาะตอน Deploy      |
| Production Web Service                  | `WEBSERVER01`                      |
