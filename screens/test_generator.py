"""ИИ-генератор тестов."""
import asyncio
import flet as ft
from models.user import app_state
from services.gemini_service import gemini

class TestGeneratorScreen(ft.View):
    def __init__(self,page,on_navigate):
        super().__init__(route="/ai_test")
        self.page=page; self.on_navigate=on_navigate; self.user=app_state.current_user
        self.build_ui()

    def build_ui(self):
        self.topic=ft.TextField(label="Тема",width=420)
        self.subject=ft.TextField(label="Предмет",value="",width=420)
        self.count=ft.Dropdown(label="Количество",value="15",options=[ft.dropdown.Option(str(x)) for x in [10,15,20]],width=150)
        self.output=ft.Column(spacing=10)
        self.loading=ft.ProgressRing(visible=False)
        self.controls=[ft.AppBar(leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self.page.go("/teacher")), title=ft.Text("AI Генератор тестов")),
            ft.Container(content=ft.Column([ft.Text("Создай тест для самопроверки",size=20,weight=ft.FontWeight.BOLD),
                self.topic,self.subject,ft.Row([self.count,ft.ElevatedButton("Сгенерировать",icon=ft.icons.AUTO_AWESOME,on_click=self.generate),self.loading]),
                ft.Divider(),self.output],scroll=ft.ScrollMode.AUTO,spacing=12),padding=15,expand=True)]

    async def _run(self):
        try:
            questions=await asyncio.to_thread(gemini.generate_test,self.topic.value.strip(),self.subject.value.strip() or "школьный предмет",int(self.count.value))
            self.output.controls=[]
            if not questions: self.output.controls.append(ft.Text("ИИ не вернул корректный тест. Попробуйте ещё раз."))
            for i,q in enumerate(questions,1):
                opts=q.get("options",[])
                self.output.controls.append(ft.Card(content=ft.Container(content=ft.Column([
                    ft.Text(f"{i}. {q.get('question','')}",weight=ft.FontWeight.BOLD),
                    ft.RadioGroup(content=ft.Column([ft.Radio(value=str(j),label=str(o)) for j,o in enumerate(opts)])),
                    ft.Text(q.get("explanation",""),size=11,color=ft.colors.ON_SURFACE_VARIANT)
                ]),padding=12)))
        except Exception as ex: self.output.controls=[ft.Text(f"Ошибка: {ex}",color=ft.colors.RED)]
        self.loading.visible=False; self.page.update()

    def generate(self,e):
        if not self.topic.value.strip():
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Введите тему."))); return
        self.loading.visible=True; self.page.update(); self.page.run_task(self._run)
