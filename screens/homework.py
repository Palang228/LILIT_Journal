"""Домашние задания"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import flet as ft

from models.user import app_state
from services.gemini_service import gemini
from services.supabase_client import supabase
from components.topbar import TopBar


class HomeworkScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/homework")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.source_files = []
        self.build_ui()

    def _back(self):
        if self.user.role == "teacher":
            target = "/teacher_class" if getattr(app_state, "selected_teacher_class", None) else "/teacher"
            self.page.go(target)
        elif self.user.role == "parent":
            self.page.go("/parent")
        else:
            self.page.go("/schedule")

    def build_ui(self):
        if self.user.role == "teacher":
            self.build_teacher()
        else:
            self.build_student()

    # -------------------- УЧЕНИК --------------------
    def build_student(self):
        items = ft.Column(spacing=10)
        try:
            homeworks = (supabase.get_homeworks(class_name=self.user.class_name).data or [])
            submissions = (supabase.get_submissions(student_id=self.user.user_id).data or [])
            submitted_ids = {s.get("homework_id") for s in submissions}
            for hw in homeworks:
                subject = (hw.get("subjects") or {}).get("name", "Предмет")
                title = hw.get("topic") or hw.get("paragraph") or "Домашнее задание"
                exercise = hw.get("exercise") or ""
                due = hw.get("due_date") or "без дедлайна"
                task_type = hw.get("task_type") or "photo"
                done = hw.get("id") in submitted_ids
                if task_type == "test":
                    action = ft.ElevatedButton(
                        "Сдано" if done else "Ответить",
                        icon=ft.icons.CHECK_CIRCLE if done else ft.icons.QUIZ,
                        disabled=done,
                        on_click=lambda e, hid=hw.get("id"): self.open_test(hid),
                    )
                elif task_type == "text":
                    action = ft.ElevatedButton(
                        "Сдано" if done else "Ответить",
                        icon=ft.icons.CHECK_CIRCLE if done else ft.icons.EDIT,
                        disabled=done,
                        on_click=lambda e, hid=hw.get("id"): self.open_text_submission(hid),
                    )
                else:
                    action = ft.ElevatedButton(
                        "Сдано" if done else "Отправить",
                        icon=ft.icons.CHECK_CIRCLE if done else ft.icons.UPLOAD_FILE,
                        disabled=done,
                        on_click=lambda e, hid=hw.get("id"): self.open_photo_submission(hid),
                    )
                items.controls.append(ft.Card(content=ft.Container(content=ft.Column([
                    ft.Row([
                        ft.Text(f"{subject}: {title}", size=17, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Container(
                            content=ft.Text("ТЕСТ" if task_type == "test" else "ДЗ", size=10, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.colors.PRIMARY_CONTAINER, border_radius=10,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        ),
                    ]),
                    ft.Text(exercise) if exercise else ft.Container(),
                    ft.Text(f"Дедлайн: {due}", size=12, color=ft.colors.ON_SURFACE_VARIANT),
                    ft.Row([action], alignment=ft.MainAxisAlignment.END),
                ], spacing=7), padding=14)))
            if not items.controls:
                items.controls.append(ft.Text("Домашних заданий пока нет."))
        except Exception as ex:
            items.controls.append(ft.Text(f"Ошибка: {ex}", color=ft.colors.RED))

        self.controls = [
            TopBar("Домашние задания", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self._back())),
            ft.Container(content=ft.Column([items], scroll=ft.ScrollMode.AUTO, spacing=15), padding=15, expand=True),
        ]

    def open_test(self, homework_id):
        app_state.selected_homework_id = homework_id
        self.page.go("/homework_test")

    def open_photo_submission(self, homework_id):
        app_state.selected_homework_id = homework_id
        self.page.go("/homework_submit")

    def open_text_submission(self, homework_id):
        app_state.selected_homework_id = homework_id
        self.page.go("/homework_text")

    # -------------------- УЧИТЕЛЬ --------------------
    def build_teacher(self):
        self.subject = ft.Dropdown(label="Предмет", width=360)
        self.class_select = ft.Dropdown(label="Класс", width=360, on_change=self._on_class_change)
        self.topic = ft.TextField(label="Тема / название", width=360)
        self.paragraph = ft.TextField(label="Параграф или материал", multiline=True, min_lines=2, max_lines=4, width=360)
        self.exercise = ft.TextField(label="Что сделать ученику", multiline=True, min_lines=2, max_lines=4, width=360)
        self.due = ft.TextField(label="Дедлайн YYYY-MM-DD HH:MM", width=360)
        self.files_text = ft.Text("Можно добавить фотографии параграфа", size=12, color=ft.colors.ON_SURFACE_VARIANT)
        self.message = ft.Text("")
        self.loading = ft.ProgressRing(visible=False)
        self.file_picker = ft.FilePicker(on_result=self.on_source_files_picked)
        self.page.overlay.append(self.file_picker)

        self.assignments = []
        self._load_teacher_filters()
        selected = getattr(app_state, "selected_teacher_class", None)
        if selected and selected in [x.key for x in self.class_select.options]:
            self.class_select.value = selected
            self._on_class_change()
        elif len(self.class_select.options) == 1:
            self.class_select.value = self.class_select.options[0].key
            self._on_class_change()

        form = ft.Column([
            ft.Text("Новое домашнее задание", size=21, weight=ft.FontWeight.BOLD),
            ft.Text("Выберите класс и просто опишите задание. AI сам определит, нужен тест или обычная сдача.", size=12, color=ft.colors.ON_SURFACE_VARIANT),
            self.class_select,
            self.subject,
            self.topic,
            self.paragraph,
            self.exercise,
            self.due,
            ft.Row([
                ft.ElevatedButton("Добавить фотографии", icon=ft.icons.IMAGE, on_click=lambda e: self.file_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.IMAGE)),
                self.files_text,
            ], wrap=True),
            ft.Row([self.loading], alignment=ft.MainAxisAlignment.CENTER),
            ft.ElevatedButton("Опубликовать", icon=ft.icons.SEND, on_click=self.create),
            self.message,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)

        self.controls = [
            TopBar("Домашнее задание", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self._back())),
            ft.Container(content=ft.Column([
                form,
                ft.Divider(height=20),
                ft.Text("Последние задания", size=18, weight=ft.FontWeight.BOLD),
                self._teacher_list(),
            ], scroll=ft.ScrollMode.AUTO, spacing=12), padding=15, expand=True),
        ]

    def _load_teacher_filters(self):
        try:
            self.assignments = supabase.get_teacher_assignments(self.user.user_id).data or []
            if not self.assignments and self.user.class_name and self.user.subject_id:
                self.assignments = [{"class_name": self.user.class_name, "subject_id": self.user.subject_id, "subjects": {"name": "Предмет"}}]
            classes = sorted({a.get("class_name") for a in self.assignments if a.get("class_name")})
            self.class_select.options = [ft.dropdown.Option(c, c) for c in classes]
        except Exception as ex:
            self.message.value = f"Не удалось загрузить классы: {ex}"

    def _on_class_change(self, e=None):
        cls = self.class_select.value
        allowed = []
        for a in self.assignments:
            if a.get("class_name") == cls and a.get("subject_id"):
                pair = (a.get("subject_id"), (a.get("subjects") or {}).get("name", "Предмет"))
                if pair not in allowed:
                    allowed.append(pair)
        self.subject.options = [ft.dropdown.Option(sid, name) for sid, name in allowed]
        self.subject.value = allowed[0][0] if allowed else None
        self.page.update()

    def on_source_files_picked(self, e):
        self.source_files = list(e.files or [])
        self.files_text.value = f"Страниц добавлено: {len(self.source_files)}" if self.source_files else "Можно добавить фотографии параграфа"
        self.page.update()

    def _teacher_list(self):
        col = ft.Column(spacing=0)
        try:
            rows = supabase.get_homeworks(teacher_id=self.user.user_id).data or []
            for h in rows[:20]:
                subject = (h.get("subjects") or {}).get("name", "Предмет")
                label = "Тест" if h.get("task_type") == "test" else "Фото"
                col.controls.append(ft.ListTile(
                    leading=ft.Icon(ft.icons.QUIZ if label == "Тест" else ft.icons.ASSIGNMENT),
                    title=ft.Text(h.get("topic") or "Без названия"),
                    subtitle=ft.Text(f"{h.get('class_name', '—')} • {subject} • {label}"),
                ))
            if not col.controls:
                col.controls.append(ft.Text("Заданий пока нет.", color=ft.colors.ON_SURFACE_VARIANT))
        except Exception as ex:
            col.controls.append(ft.Text(f"Ошибка: {ex}", color=ft.colors.RED))
        return col

    @staticmethod
    def _infer_type(topic, paragraph, exercise, has_images):
        if has_images:
            return "test"
        text = f"{topic} {paragraph} {exercise}".lower()
        return "test" if any(word in text for word in ("тест", "проверка знаний", "контрольная", "вопросы")) else "photo"

    async def _create_async(self):
        try:
            parsed = datetime.fromisoformat(self.due.value.strip()) if self.due.value.strip() else datetime.now(timezone.utc) + timedelta(days=1)
            due_dt = (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed).isoformat()
            has_images = bool(self.source_files)
            task_type = self._infer_type(self.topic.value, self.paragraph.value, self.exercise.value, has_images)
            source_urls, image_bytes, source_text, test_questions = [], [], None, []

            for f in self.source_files:
                with open(f.path, "rb") as fp:
                    data = fp.read()
                image_bytes.append(data)
                ext = os.path.splitext(f.name or "jpg")[1] or ".jpg"
                path = f"teachers/{self.user.user_id}/{uuid.uuid4().hex}{ext}"
                supabase.upload_file("homeworks", path, data, "image/jpeg")
                source_urls.append(supabase.get_public_url("homeworks", path))

            if image_bytes:
                self.message.value = "AI читает фотографии параграфа и собирает тест…"
                self.page.update()
                result = await asyncio.to_thread(
                    gemini.generate_test_from_images,
                    image_bytes,
                    self._selected_subject_name(),
                    self.exercise.value.strip() or self.paragraph.value.strip(),
                    15,
                )
                source_text = result.get("source_text") or None
                test_questions = result.get("questions") or []
                if not test_questions:
                    raise RuntimeError("AI не смог создать тест по фотографиям параграфа.")
                task_type = "test"
            elif task_type == "test":
                self.message.value = "AI создаёт тест…"
                self.page.update()
                test_questions = await asyncio.to_thread(
                    gemini.generate_test,
                    self.topic.value.strip() or self.paragraph.value.strip() or self.exercise.value.strip(),
                    self._selected_subject_name(),
                    15,
                )
                if not test_questions:
                    raise RuntimeError("AI не вернул вопросы.")

            payload = {
                "class_name": self.class_select.value,
                "subject_id": self.subject.value,
                "teacher_id": self.user.user_id,
                "topic": self.topic.value.strip() or ("Проверочный тест" if task_type == "test" else "Домашнее задание"),
                "paragraph": self.paragraph.value.strip() or None,
                "exercise": self.exercise.value.strip() or ("Ответить на вопросы" if task_type == "test" else "Выполнить задание"),
                "note": None,
                "due_date": due_dt,
                "task_type": task_type,
                "test_questions": test_questions,
                "source_images": source_urls,
                "source_text": source_text,
                "ai_status": "ready" if test_questions else "none",
            }
            supabase.create_homework(payload)
            self.message.value = "Задание опубликовано ✅"
            self.topic.value = self.paragraph.value = self.exercise.value = ""
            self.source_files = []
            self.files_text.value = "Можно добавить фотографии параграфа"
            self.page.update()
        except Exception as ex:
            self.message.value = f"Ошибка публикации: {ex}"
        finally:
            self.loading.visible = False
            self.page.update()

    def _selected_subject_name(self):
        for opt in self.subject.options:
            if opt.key == self.subject.value:
                return opt.text or "Школьный предмет"
        return "Школьный предмет"

    def create(self, e):
        if not self.class_select.value:
            self.message.value = "Выберите класс."
        elif not self.subject.value:
            self.message.value = "Выберите предмет."
        elif not (self.topic.value.strip() or self.paragraph.value.strip() or self.exercise.value.strip() or self.source_files):
            self.message.value = "Опишите задание или добавьте фотографии."
        else:
            self.loading.visible = True
            self.message.value = "Подготавливаем…"
            self.page.update()
            self.page.run_task(self._create_async)
