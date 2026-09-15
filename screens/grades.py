"""Электронный журнал"""
import flet as ft
from collections import defaultdict
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar


class GradesScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/grades")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.teacher_assignments = []
        self.build_ui()

    def _back(self):
        role = self.user.role
        self.page.go({"teacher": "/teacher", "parent": "/parent"}.get(role, "/schedule"))

    def build_ui(self):
        if self.user.role == "teacher":
            self.build_teacher_view()
        elif self.user.role == "parent":
            self.build_parent_view()
        else:
            self.build_student_view()

    def build_student_view(self):
        self.grades_list = ft.Column(spacing=8)
        try:
            marks = supabase.get_marks(student_id=self.user.user_id).data or []
            by_subject = defaultdict(list)
            for m in marks:
                try:
                    by_subject[(m.get("subjects") or {}).get("name", "Неизвестно")].append(float(m.get("value")))
                except (TypeError, ValueError):
                    pass
            for subject, vals in by_subject.items():
                avg = sum(vals) / len(vals)
                self.grades_list.controls.append(ft.Card(content=ft.Container(content=ft.Column([
                    ft.Row([
                        ft.Text(subject, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(f"{avg:.2f}", color=ft.colors.PRIMARY, weight=ft.FontWeight.BOLD)
                    ]),
                    ft.Text("Оценки: " + "  ".join(str(int(v)) if v.is_integer() else str(v) for v in vals))
                ]), padding=14)))
            if not self.grades_list.controls:
                self.grades_list.controls.append(ft.Text("Пока нет оценок."))
        except Exception as ex:
            self.grades_list.controls.append(ft.Text(f"Ошибка: {ex}", color=ft.colors.RED))

        self.target = ft.Slider(min=2, max=5, divisions=6, value=4.5, label="{value}")
        self.future = ft.Dropdown(label="Будущих оценок", value="3",
                                  options=[ft.dropdown.Option(str(x)) for x in range(1, 11)], width=180)
        self.forecast = ft.Text("")
        card = ft.Card(content=ft.Container(content=ft.Column([
            ft.Text("🎯 Цель на ближайшие оценки", size=16, weight=ft.FontWeight.BOLD),
            self.target, self.future,
            ft.ElevatedButton("Рассчитать", icon=ft.icons.CALCULATE, on_click=self.calculate_target),
            self.forecast
        ]), padding=14))
        self.controls = [
            TopBar("Мои оценки"),
            ft.Container(content=ft.Column([card, self.grades_list], scroll=ft.ScrollMode.AUTO, spacing=12),
                         padding=15, expand=True)
        ]

    def calculate_target(self, e):
        try:
            marks = supabase.get_marks(student_id=self.user.user_id).data or []
            vals = [float(m["value"]) for m in marks if m.get("value") is not None]
            target = float(self.target.value)
            k = int(self.future.value)
            n = len(vals)
            if not vals:
                self.forecast.value = "Нет текущих оценок — ориентируйтесь на цель."
                self.page.update()
                return
            needed = (target * (n + k) - sum(vals)) / k
            if needed <= 2:
                msg = f"Для цели {target:.1f} достаточно в среднем {max(2, needed):.2f} за следующие {k} оценок."
            elif needed > 5:
                msg = f"Цель {target:.1f} за {k} оценок математически недостижима без пересмотра старых оценок."
            else:
                msg = f"Нужно в среднем {needed:.2f} за следующие {k} оценок."
            self.forecast.value = msg
            self.page.update()
        except Exception as ex:
            self.forecast.value = f"Ошибка: {ex}"
            self.page.update()

    def build_teacher_view(self):
        self.class_select = ft.Dropdown(label="Класс", width=220, on_change=lambda e: self._on_teacher_filter_change())
        self.subject_select = ft.Dropdown(label="Предмет", width=240, on_change=lambda e: self._on_teacher_filter_change())
        self.category = ft.Dropdown(label="Категория", value="homework", width=220, options=[
            ft.dropdown.Option("homework", "Домашнее"),
            ft.dropdown.Option("classwork", "Классная"),
            ft.dropdown.Option("quarterly", "Четвертная"),
            ft.dropdown.Option("annual", "Годовая"),
            ft.dropdown.Option("behavior", "Поведение")
        ], on_change=lambda e: self.load_teacher_marks())
        self.table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("Ученик")), ft.DataColumn(ft.Text("Оценка")), ft.DataColumn(ft.Text("Комментарий"))],
            rows=[]
        )
        self.info = ft.Text("Выберите класс и предмет.", color=ft.colors.ON_SURFACE_VARIANT)
        self.controls = [
            TopBar("Журнал", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self._back())),
            ft.Container(content=ft.Column([
                ft.Row([self.class_select, self.subject_select], wrap=True),
                ft.Row([
                    self.category,
                    ft.ElevatedButton("Добавить оценку", icon=ft.icons.ADD, on_click=self.add_mark_dialog)
                ], wrap=True),
                self.info,
                ft.Row([self.table], scroll=ft.ScrollMode.AUTO),
            ], scroll=ft.ScrollMode.AUTO, spacing=10), padding=15, expand=True)
        ]
        self._load_assignments()

    def _load_assignments(self):
        try:
            self.teacher_assignments = supabase.get_teacher_assignments(self.user.user_id).data or []
            if not self.teacher_assignments and self.user.class_name:
                self.teacher_assignments = [{"class_name": self.user.class_name, "subject_id": self.user.subject_id,
                                             "subjects": {"name": "Предмет"}}]
            classes = []
            subjects = []
            for a in self.teacher_assignments:
                cls = a.get("class_name")
                sid = a.get("subject_id")
                sname = (a.get("subjects") or {}).get("name", "Предмет")
                if cls and cls not in classes:
                    classes.append(cls)
                if sid and sid not in {x[0] for x in subjects}:
                    subjects.append((sid, sname))
            self.class_select.options = [ft.dropdown.Option(c, c) for c in classes]
            self.subject_select.options = [ft.dropdown.Option(sid, name) for sid, name in subjects]
            selected_class = getattr(app_state, "selected_teacher_class", None)
            if selected_class in classes:
                self.class_select.value = selected_class
            elif len(classes) == 1:
                self.class_select.value = classes[0]
            if len(subjects) == 1:
                self.subject_select.value = subjects[0][0]
            self.load_teacher_marks()
        except Exception as ex:
            self.info.value = f"Ошибка загрузки закреплений: {ex}"
            self.page.update()

    def _on_teacher_filter_change(self):
        # После выбора класса оставляем только предметы, которыми этот учитель действительно занимается в классе.
        if self.class_select.value:
            allowed = [(a.get("subject_id"), (a.get("subjects") or {}).get("name", "Предмет"))
                       for a in self.teacher_assignments if a.get("class_name") == self.class_select.value]
            if allowed:
                self.subject_select.options = [ft.dropdown.Option(sid, name) for sid, name in allowed]
                if self.subject_select.value not in {sid for sid, _ in allowed}:
                    self.subject_select.value = allowed[0][0]
        self.load_teacher_marks()

    def load_teacher_marks(self):
        if not getattr(self, "class_select", None) or not self.class_select.value or not self.subject_select.value:
            self.info.value = "Выберите класс и предмет."
            self.page.update()
            return
        try:
            marks = supabase.get_marks(class_name=self.class_select.value,
                                       subject_id=self.subject_select.value,
                                       category=self.category.value).data or []
            self.table.rows = []
            for m in marks:
                name = (m.get("student") or {}).get("full_name", "Ученик")
                self.table.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(str(m.get("value", "")))),
                    ft.DataCell(ft.Text(m.get("comment") or "—")),
                ]))
            self.info.value = f"{self.class_select.value} • {(self.subject_select.value or '')} • записей: {len(marks)}"
            self.page.update()
        except Exception as ex:
            self.page.show_snack_bar(ft.SnackBar(ft.Text(f"Ошибка загрузки: {ex}")))

    def add_mark_dialog(self, e):
        if not self.class_select.value or not self.subject_select.value:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Сначала выберите класс и предмет.")))
            return
        try:
            students = supabase.get_profiles_by_class(self.class_select.value).data or []
        except Exception:
            students = []
        student = ft.Dropdown(label="Ученик", width=320,
                              options=[ft.dropdown.Option(s["id"], s.get("full_name", "")) for s in students if s.get("role") == "student"])
        value = ft.TextField(label="Оценка 2–5", width=150)
        comment = ft.TextField(label="Комментарий", multiline=True)

        def close(e):
            dlg.open = False
            self.page.update()

        def save(e):
            try:
                v = float(value.value)
                if not student.value or not 2 <= v <= 5:
                    raise ValueError("Выберите ученика и введите оценку от 2 до 5.")
                supabase.add_mark({
                    "student_id": student.value,
                    "subject_id": self.subject_select.value,
                    "value": v,
                    "category": self.category.value,
                    "comment": comment.value.strip() or None,
                    "teacher_id": self.user.user_id,
                    "class_name": self.class_select.value,
                })
                close(e)
                self.load_teacher_marks()
            except Exception as ex:
                self.page.show_snack_bar(ft.SnackBar(ft.Text(str(ex))))

        dlg = ft.AlertDialog(title=ft.Text("Новая оценка"), content=ft.Column([student, value, comment], tight=True),
                             actions=[ft.TextButton("Отмена", on_click=close), ft.ElevatedButton("Сохранить", on_click=save)])
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def build_parent_view(self):
        content = ft.Column(spacing=10)
        try:
            children = supabase.get_children(self.user.user_id).data or []
            for child in children:
                marks = supabase.get_marks(student_id=child["id"]).data or []
                by = defaultdict(list)
                for m in marks:
                    try:
                        by[(m.get("subjects") or {}).get("name", "Предмет")].append(float(m.get("value")))
                    except Exception:
                        pass
                rows = [ft.Text(child.get("full_name", "Ребёнок"), size=17, weight=ft.FontWeight.BOLD)]
                rows += [ft.Text(f"{s}: {sum(v) / len(v):.2f}") for s, v in by.items()]
                content.controls.append(ft.Card(content=ft.Container(content=ft.Column(rows), padding=14)))
            if not children:
                content.controls.append(ft.Text("Нет привязанных детей."))
        except Exception as ex:
            content.controls.append(ft.Text(f"Ошибка: {ex}", color=ft.colors.RED))
        self.controls = [
            TopBar("Успеваемость"),
            ft.Container(content=content, padding=15, expand=True)
        ]
