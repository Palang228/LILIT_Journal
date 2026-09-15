"""расписание"""
import flet as ft
from datetime import datetime, timedelta
from models.user import app_state
from services.supabase_client import supabase
from components.navbar import BottomNavBar
from components.topbar import TopBar

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]


class ScheduleScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/schedule")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.days_column = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO)
        self.teacher_class = getattr(app_state, "selected_teacher_class", None)
        self.build_ui()
        self.page.run_task(self._load_async)

    def build_ui(self):
        title = "Расписание"
        if self.user.role == "teacher":
            title = "Расписание учителя"
        self.controls = [
            ft.Column([
                TopBar(title, actions=[ft.IconButton(ft.icons.PERSON, tooltip="Профиль", on_click=lambda e: self.on_navigate("profile"))]),
                ft.Container(content=self.days_column, padding=14, expand=True),
                BottomNavBar(self.page, self.on_navigate, active_tab="schedule"),
            ], expand=True, spacing=0)
        ]

    async def _load_async(self):
        import asyncio
        try:
            # 1) Сначала отрисовываем локальный кэш. На повторном запуске это практически мгновенно.
            if self.user.role == "teacher":
                data = await asyncio.to_thread(self._fetch_teacher_week, False)
                self._render_teacher_week(*data)
            else:
                data = await asyncio.to_thread(self._fetch_student_week, False)
                self._render_student_week(*data)
            self.page.update()

            # 2) Затем одним фоновым проходом перечитываем свежие данные из Supabase.
            if self.user.role == "teacher":
                fresh = await asyncio.to_thread(self._fetch_teacher_week, True)
                self._render_teacher_week(*fresh)
            else:
                fresh = await asyncio.to_thread(self._fetch_student_week, True)
                self._render_student_week(*fresh)
        except Exception as ex:
            # Если кэш уже отрисован, не стираем его из-за временной сетевой ошибки.
            if not self.days_column.controls:
                self.days_column.controls = [ft.Text(f"Ошибка загрузки расписания: {ex}", color=ft.colors.RED)]
        self.page.update()

    def _week_date(self, index):
        monday = datetime.now() - timedelta(days=datetime.now().weekday())
        return (monday + timedelta(days=index)).strftime("%d.%m")

    def _fetch_student_week(self, fresh=False):
        try:
            profile = supabase.refresh_profile(self.user.user_id) or {}
            self.user.metadata = profile or self.user.metadata
            self.user.class_name = supabase.infer_test_class(self.user.email, profile.get("class_name") if profile else self.user.class_name)
            app_state.set_user(self.user)
        except Exception:
            # Даже без сети используем уже сохранённый профиль, но исправляем тестовые аккаунты.
            self.user.class_name = supabase.infer_test_class(self.user.email, self.user.class_name)
            app_state.set_user(self.user)
        if not self.user.class_name:
            return [], [], [], []
        from concurrent.futures import ThreadPoolExecutor

        def unwrap(value):
            return value if isinstance(value, list) else (value.data or [])

        timetable_fn = (lambda: supabase.refresh_timetable_week(self.user.class_name)) if fresh else (lambda: supabase.get_timetable_week(self.user.class_name))
        hw_fn = (lambda: self._fresh_homeworks(self.user.class_name)) if fresh else (lambda: supabase.get_homeworks(class_name=self.user.class_name))
        marks_fn = (lambda: self._fresh_marks(self.user.user_id)) if fresh else (lambda: supabase.get_marks(student_id=self.user.user_id))
        sub_fn = (lambda: self._fresh_submissions(self.user.user_id)) if fresh else (lambda: supabase.get_submissions(student_id=self.user.user_id))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fn) for fn in (timetable_fn, hw_fn, marks_fn, sub_fn)]
            values = [future.result() for future in futures]
        return tuple(unwrap(v) for v in values)

    def _fresh_homeworks(self, class_name):
        res = supabase.client.table("homeworks").select("*, subjects(name), profiles(full_name)").eq("class_name", class_name).order("due_date").execute()
        data = res.data or []
        supabase.cache.set(f"homeworks:{class_name}:*:*", data)
        return data

    def _fresh_marks(self, student_id):
        # Вызов сервиса здесь уже сбрасывает кэш не требуется; SupabaseService отдаёт свежий результат при cache miss.
        res = supabase.client.table("marks").select("id,value,category,comment,created_at,class_name,student_id,subject_id,teacher_id,subjects(name)").eq("student_id", student_id).order("created_at", desc=True).execute()
        data = res.data or []
        supabase.cache.set(f"marks:{student_id}:*:*:*", data)
        return data

    def _fresh_submissions(self, student_id):
        res = supabase.client.table("submissions").select("*, profiles(full_name), homeworks(topic,paragraph,exercise,due_date,task_type,test_questions,teacher_id,class_name)").eq("student_id", student_id).order("submitted_at", desc=True).execute()
        data = res.data or []
        supabase.cache.set(f"submissions:*:{student_id}:*", data)
        return data

    def _render_student_week(self, timetable, homeworks, marks, submissions):
        self.days_column.controls.clear()
        if not self.user.class_name:
            self.days_column.controls.append(ft.Text("Класс не назначен."))
            return
        for day in range(1, 7):
            lessons = [x for x in timetable if x.get("day_of_week") == day]
            self.days_column.controls.append(self._student_day(day - 1, lessons, homeworks, marks, submissions))

    def _student_day(self, day_index, lessons, homeworks, marks, submissions):
        rows = []
        for lesson in lessons:
            subject_id = lesson.get("subject_id")
            subject = (lesson.get("subjects") or {}).get("name", "Предмет")
            hw = next((h for h in homeworks if h.get("subject_id") == subject_id), None)
            submission = next((s for s in submissions if hw and s.get("homework_id") == hw.get("id")), None) if hw else None
            values = [m.get("value") for m in marks if m.get("subject_id") == subject_id][:2]
            mark_boxes = [self._mark_box(v) for v in values]
            while len(mark_boxes) < 2:
                mark_boxes.append(ft.Container(width=34, height=30))
            action = self._student_action(hw, submission)
            rows.append(ft.Row([
                ft.Container(ft.Text(str(lesson.get("lesson_number", "")), weight=ft.FontWeight.BOLD), width=28),
                ft.Column([
                    ft.Text(subject, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text((hw or {}).get("topic") or (hw or {}).get("paragraph") or "", size=12, color=ft.colors.ON_SURFACE_VARIANT),
                ], expand=True, spacing=1),
                ft.Column([ft.Row(mark_boxes, spacing=4), action], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
            ]))
            rows.append(ft.Divider(height=5, color=ft.colors.TRANSPARENT))
        if not rows:
            rows = [ft.Text("Нет занятий", color=ft.colors.ON_SURFACE_VARIANT)]
        return self._day_card(DAYS_RU[day_index], self._week_date(day_index), rows)

    def _teacher_day(self, day_index, lessons):
        rows = []
        for lesson in lessons:
            subject = (lesson.get("subjects") or {}).get("name", "Предмет")
            rows.append(ft.Row([
                ft.Container(ft.Text(str(lesson.get("lesson_number", "")), weight=ft.FontWeight.BOLD), width=28),
                ft.Column([
                    ft.Text(subject, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(lesson.get("class_name") or self.teacher_class or "Класс", size=12, color=ft.colors.ON_SURFACE_VARIANT),
                ], expand=True),
            ]))
            rows.append(ft.Divider(height=5, color=ft.colors.TRANSPARENT))
        if not rows:
            rows = [ft.Text("Нет занятий", color=ft.colors.ON_SURFACE_VARIANT)]
        return self._day_card(DAYS_RU[day_index], self._week_date(day_index), rows)

    def _day_card(self, day_name, date, rows):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Text(day_name, size=16, weight=ft.FontWeight.BOLD), ft.Text(date, size=12, color=ft.colors.ON_SURFACE_VARIANT)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=8),
                ft.Column(rows, spacing=0),
            ], spacing=6),
            padding=15,
            bgcolor=ft.colors.SURFACE,
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=16,
        )

    def _mark_box(self, value):
        text = "" if value is None else str(int(float(value))) if float(value).is_integer() else str(value)
        return ft.Container(content=ft.Text(text, weight=ft.FontWeight.BOLD), width=34, height=30, border=ft.border.all(1, ft.colors.OUTLINE), border_radius=6, alignment=ft.alignment.center)

    def _student_action(self, hw, submission):
        if not hw:
            return ft.Container(width=90, height=28)
        done = bool(submission)
        typ = hw.get("task_type") or "photo"
        label = "Сдано" if done else ("Ответить" if typ in ("test", "text") else "Отправить")
        def go(_):
            app_state.selected_homework_id = hw.get("id")
            self.page.go("/homework_test" if typ == "test" else "/homework_text" if typ == "text" else "/homework_submit")
        return ft.TextButton(label, disabled=done, on_click=go)

    def _fetch_teacher_week(self, fresh=False):
        assignments = (supabase.refresh_teacher_assignments(self.user.user_id) if fresh else (supabase.get_teacher_assignments(self.user.user_id).data or []))
        classes = sorted({x.get("class_name") for x in assignments if x.get("class_name")})
        selected = self.teacher_class if self.teacher_class in classes else (classes[0] if len(classes) == 1 else self.teacher_class)
        timetable = []
        if selected:
            all_lessons = supabase.refresh_timetable_week(selected) if fresh else (supabase.get_timetable_week(selected).data or [])
            allowed_subjects = {a.get("subject_id") for a in assignments if a.get("class_name") == selected}
            timetable = [x for x in all_lessons if x.get("subject_id") in allowed_subjects]
        return assignments, classes, selected, timetable

    def _render_teacher_week(self, assignments, classes, selected, timetable):
        self.days_column.controls.clear()
        if len(classes) > 1:
            self.days_column.controls.append(ft.Dropdown(
                label="Класс", value=selected, options=[ft.dropdown.Option(c, c) for c in classes],
                on_change=self._teacher_class_changed,
            ))
        if not selected:
            self.days_column.controls.append(ft.Text("Выберите класс, чтобы открыть расписание.", color=ft.colors.ON_SURFACE_VARIANT))
            return
        self.teacher_class = selected
        for day in range(1, 7):
            lessons = [x for x in timetable if x.get("day_of_week") == day]
            self.days_column.controls.append(self._teacher_day(day - 1, lessons))

    def _load_teacher_week(self):
        data = self._fetch_teacher_week()
        self._render_teacher_week(*data)

    def _teacher_class_changed(self, e):
        app_state.selected_teacher_class = e.control.value
        self.teacher_class = e.control.value
        self._load_teacher_week()
        self.page.update()
