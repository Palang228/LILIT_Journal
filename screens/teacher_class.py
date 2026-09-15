"""Экран конкретного класса учителя."""
import flet as ft
from datetime import datetime
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar


class TeacherClassScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/teacher_class")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.class_name = getattr(app_state, "selected_teacher_class", None) or self.user.class_name
        self.build_ui()

    def _back(self):
        self.page.go("/teacher")

    def build_ui(self):
        stats = self._stats()
        homeworks = self._homeworks()
        students = self._students()
        self.controls = [
            ft.Column([
                TopBar(self.class_name or "Класс", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self._back()), actions=[ft.IconButton(ft.icons.PERSON, tooltip="Профиль", on_click=lambda e: self.on_navigate("profile"))]),
                ft.Container(
                    content=ft.Column([
                        ft.Text(self.class_name or "Класс", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("Успеваемость и домашние задания класса", size=13, color=ft.colors.ON_SURFACE_VARIANT),
                        self._stats_row(stats),
                        ft.Divider(height=20),
                        ft.Row([
                            ft.Text("Домашние задания", size=18, weight=ft.FontWeight.BOLD, expand=True),
                            ft.TextButton("Все задания", on_click=lambda e: self._open_homework()),
                        ]),
                        self._homework_list(homeworks),
                        ft.Divider(height=20),
                        ft.Row([
                            ft.Text("Ученики", size=18, weight=ft.FontWeight.BOLD, expand=True),
                            ft.TextButton("Журнал", on_click=lambda e: self._open_grades()),
                        ]),
                        self._student_list(students),
                    ], scroll=ft.ScrollMode.AUTO, spacing=10),
                    padding=20,
                    expand=True,
                ),
            ], expand=True, spacing=0)
        ]

    def _stats(self):
        from concurrent.futures import ThreadPoolExecutor
        students = self._students()
        homeworks = self._homeworks()
        if not homeworks:
            return {"students": len(students), "homeworks": 0, "submitted": 0, "checked": 0}
        def load(hw):
            try:
                return supabase.get_submissions(homework_id=hw.get("id")).data or []
            except Exception:
                return []
        with ThreadPoolExecutor(max_workers=min(8, len(homeworks))) as pool:
            all_subs = list(pool.map(load, homeworks))
        submissions = [s for group in all_subs for s in group]
        return {"students": len(students), "homeworks": len(homeworks),
                "submitted": len(submissions),
                "checked": sum(1 for s in submissions if s.get("status") == "checked")}

    def _students(self):
        try:
            rows = supabase.get_students_for_class(self.class_name)
            return rows
        except Exception:
            return []

    def _homeworks(self):
        try:
            return supabase.get_homeworks(class_name=self.class_name, teacher_id=self.user.user_id).data or []
        except Exception:
            return []

    def _stats_row(self, stats):
        data = [("Ученики", stats["students"], ft.icons.PEOPLE), ("ДЗ", stats["homeworks"], ft.icons.ASSIGNMENT), ("Сдано", stats["submitted"], ft.icons.SEND), ("Проверено", stats["checked"], ft.icons.CHECK_CIRCLE)]
        cards = []
        for label, value, icon in data:
            cards.append(ft.Container(
                content=ft.Row([ft.Icon(icon, size=20, color=ft.colors.DEEP_PURPLE), ft.Column([ft.Text(str(value), size=20, weight=ft.FontWeight.BOLD), ft.Text(label, size=11, color=ft.colors.ON_SURFACE_VARIANT)], spacing=0)], spacing=9),
                padding=14, border_radius=14, bgcolor=ft.colors.SURFACE_VARIANT,
            ))
        return ft.Row(cards, wrap=True, spacing=10, run_spacing=10)

    def _homework_list(self, homeworks):
        if not homeworks:
            return ft.Container(content=ft.Text("Для этого класса пока нет заданий."), padding=14, bgcolor=ft.colors.SURFACE_VARIANT, border_radius=14)
        items = []
        for hw in homeworks[:8]:
            subject = (hw.get("subjects") or {}).get("name", "Предмет")
            kind = "Тест" if hw.get("task_type") == "test" else "Фото"
            due = hw.get("due_date") or "Без дедлайна"
            items.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Icon(ft.icons.QUIZ if kind == "Тест" else ft.icons.IMAGE), bgcolor=ft.colors.PRIMARY_CONTAINER),
                title=ft.Text(hw.get("topic") or "Домашнее задание", weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"{subject} • {kind} • до {due}"),
            ))
        return ft.Column(items, spacing=0)

    def _student_list(self, students):
        if not students:
            return ft.Text("Ученики не найдены.", color=ft.colors.ON_SURFACE_VARIANT)
        try:
            all_marks = supabase.get_marks(class_name=self.class_name).data or []
        except Exception:
            all_marks = []
        marks_by_student = {}
        for m in all_marks:
            marks_by_student.setdefault(m.get("student_id"), []).append(m)
        items = []
        for s in students[:20]:
            name = s.get("full_name") or "Ученик"
            values = [float(m.get("value")) for m in marks_by_student.get(s.get("id"), []) if m.get("value") is not None]
            avg = sum(values) / len(values) if values else 0
            items.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text(name[0].upper())),
                title=ft.Text(name),
                subtitle=ft.Text(f"Средний балл: {avg:.2f}" if avg else "Оценок пока нет"),
                on_click=lambda e, sid=s.get("id"): self._open_student_grades(sid),
            ))
        return ft.Column(items, spacing=0)

    def _open_homework(self):
        self.page.go("/homework")

    def _open_grades(self):
        self.page.go("/grades")

    def _open_student_grades(self, student_id):
        app_state.selected_grade_student_id = student_id
        self.page.go("/grades")
