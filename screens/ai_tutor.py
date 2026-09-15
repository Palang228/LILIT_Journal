"""Контекстный AI-помощнник."""
import asyncio
import flet as ft
from models.user import app_state
from services.gemini_service import gemini
from components.navbar import BottomNavBar
from components.topbar import TopBar

class AITutorScreen(ft.View):
    def __init__(self,page,on_navigate):
        super().__init__(route="/ai_tutor")
        self.page=page; self.on_navigate=on_navigate; self.user=app_state.current_user
        self.build_ui()

    def build_ui(self):
        self.topic=ft.TextField(label="Тема или вопрос",hint_text="Например: Как решить квадратное уравнение?",multiline=True,min_lines=2,max_lines=4)
        self.context=ft.TextField(label="Контекст урока (необязательно)",multiline=True,min_lines=2,max_lines=5)
        self.level=ft.Dropdown(label="Уровень",value="средний",options=[ft.dropdown.Option(x) for x in ["начальный","средний","продвинутый"]],width=220)
        self.response=ft.Markdown("Здесь появится объяснение.",selectable=True)
        self.loading=ft.ProgressRing(visible=False)
        self.controls=[ft.Column([
            TopBar("Лилит — Репетитор"),
            ft.Container(content=ft.Column([
                ft.Text("🎓 Персональный репетитор",size=20,weight=ft.FontWeight.BOLD),
                self.topic,self.context,self.level,
                ft.Row([ft.ElevatedButton("Объясни мне",icon=ft.icons.SEND,on_click=self.ask_ai),self.loading]),
                ft.Divider(),
                ft.Container(content=self.response,padding=15,bgcolor=ft.colors.SURFACE_VARIANT,border_radius=12)
            ],scroll=ft.ScrollMode.AUTO,spacing=12),padding=15,expand=True),
            BottomNavBar(self.page, self.on_navigate, active_tab="ai_tutor")
        ], expand=True, spacing=0)]

    async def _ask(self):
        try:
            text=await asyncio.to_thread(gemini.tutor_explain,self.topic.value.strip(),self.context.value or "",self.level.value or "средний")
            self.response.value=text
        except Exception as ex: self.response.value=f"**Ошибка:** {ex}"
        self.loading.visible=False; self.page.update()

    def ask_ai(self,e):
        if not self.topic.value.strip():
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Введите вопрос или тему."))); return
        self.loading.visible=True; self.page.update(); self.page.run_task(self._ask)
