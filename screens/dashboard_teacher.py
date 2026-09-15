"""Дашборд учителя"""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.navbar import BottomNavBar
from components.topbar import TopBar


PRIMARY = ft.colors.DEEP_PURPLE


class TeacherDashboard(ft.View):
    def __init__(self, page: ft.Page, on_navigate):
        super().__init__(route="/teacher")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.build_ui()

    def build_ui(self):
        classes = self._teacher_classes()
        self.controls = [
            ft.Column([
                TopBar("Лилит — Учитель", actions=[
                    ft.IconButton(ft.icons.CALENDAR_TODAY, tooltip="Расписание", on_click=lambda e: self.on_navigate("schedule")),
                    ft.IconButton(ft.icons.PERSON, tooltip="Профиль", on_click=lambda e: self.on_navigate("profile")),
                ]),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Здравствуйте, {self.user.full_name}!", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("Выберите класс, чтобы открыть его журнал и домашние задания.", size=14, color=ft.colors.ON_SURFACE_VARIANT),
                        ft.Divider(height=20),
                        ft.Text("Мои классы", size=18, weight=ft.FontWeight.BOLD),
                        self._build_class_grid(classes),
                    ], spacing=10, scroll=ft.ScrollMode.AUTO),
                    padding=20,
                    expand=True,
                ),
                BottomNavBar(self.page, self.on_navigate, active_tab="teacher"),
            ], expand=True, spacing=0)
        ]

    def _teacher_classes(self):
        try:
            assignments = supabase.get_teacher_assignments(self.user.user_id).data or []
            # Если в локальном кэше раньше сохранился пустой список, сразу перепроверяем Supabase.
            if not assignments:
                assignments = supabase.refresh_teacher_assignments(self.user.user_id)
            grouped = {}
            for a in assignments:
                cls = a.get("class_name")
                if not cls:
                    continue
                grouped.setdefault(cls, [])
                subject = (a.get("subjects") or {}).get("name")
                if subject and subject not in grouped[cls]:
                    grouped[cls].append(subject)
            if not grouped and self.user.class_name:
                grouped[self.user.class_name] = []
            from concurrent.futures import ThreadPoolExecutor
            class_items = sorted(grouped.items())
            def count_students(item):
                cls, subjects = item
                try:
                    rows = supabase.get_students_for_class(cls)
                    count = len(rows)
                except Exception:
                    count = 0
                return {"class_name": cls, "subjects": subjects, "count": count}
            with ThreadPoolExecutor(max_workers=min(8, max(1, len(class_items)))) as pool:
                return list(pool.map(count_students, class_items))
        except Exception:
            return []

    def _build_class_grid(self, classes):
        if not classes:
            return ft.Container(
                content=ft.Text("У вас пока нет закреплённых классов.", color=ft.colors.ON_SURFACE_VARIANT),
                padding=20,
                border_radius=16,
                bgcolor=ft.colors.SURFACE_VARIANT,
            )
        cards = []
        palette = [
            (ft.colors.BLUE_50, ft.colors.BLUE_700),
            (ft.colors.GREEN_50, ft.colors.GREEN_700),
            (ft.colors.DEEP_PURPLE_50, ft.colors.DEEP_PURPLE_700),
            (ft.colors.ORANGE_50, ft.colors.ORANGE_700),
            (ft.colors.CYAN_50, ft.colors.CYAN_700),
            (ft.colors.PINK_50, ft.colors.PINK_700),
        ]
        for i, item in enumerate(classes):
            bg, accent = palette[i % len(palette)]
            chips = [ft.Container(
                content=ft.Text(s, size=11, color=accent),
                bgcolor=ft.colors.WHITE,
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=9, vertical=4),
            ) for s in item["subjects"][:3]]
            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.icons.GROUP, color=accent, size=22),
                            width=44, height=44, border_radius=14, bgcolor=ft.colors.WHITE,
                            alignment=ft.alignment.center,
                        ),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, color=accent),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(item["class_name"], size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{item['count']} учеников", size=12, color=ft.colors.ON_SURFACE_VARIANT),
                    ft.Row(chips, wrap=True, spacing=5) if chips else ft.Text("Предмет не указан", size=11, color=ft.colors.ON_SURFACE_VARIANT),
                ], spacing=8),
                bgcolor=bg,
                border_radius=18,
                padding=16,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
                on_click=lambda e, cls=item["class_name"]: self._open_class(cls),
                ink=True,
            )
            cards.append(card)
        return ft.Row(cards, wrap=True, spacing=12, run_spacing=12)

    def _open_class(self, class_name):
        app_state.selected_teacher_class = class_name
        self.page.go("/teacher_class")
