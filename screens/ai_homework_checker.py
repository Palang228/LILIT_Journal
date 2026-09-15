"""Проверка домашней работы по фотографии через Gemini."""
import asyncio, base64, uuid
import flet as ft
from models.user import app_state
from services.gemini_service import gemini
from services.supabase_client import supabase
from components.topbar import TopBar

class AIHomeworkChecker(ft.View):
    def __init__(self,page,on_navigate):
        super().__init__(route="/ai_homework")
        self.page=page; self.on_navigate=on_navigate; self.user=app_state.current_user
        self.image_bytes=None; self.build_ui()

    def build_ui(self):
        self.homework_dropdown=ft.Dropdown(label="Выберите задание",options=[],width=420)
        self._load_homeworks()
        self.file_picker=ft.FilePicker(on_result=self.on_file_picked); self.page.overlay.append(self.file_picker)
        self.image_preview=ft.Image(src="",width=420,height=260,fit=ft.ImageFit.COVER,border_radius=12,visible=False)
        self.score_text=ft.Text("Оценка: —/100",size=24,weight=ft.FontWeight.BOLD)
        self.feedback_text=ft.Markdown("")
        self.errors_list=ft.Column(); self.tasks_list=ft.Column()
        self.result_card=ft.Card(visible=False,content=ft.Container(content=ft.Column([
            ft.Text("📊 Результат",size=18,weight=ft.FontWeight.BOLD),self.score_text,ft.Divider(),
            ft.Text("💬 Отзыв",weight=ft.FontWeight.BOLD),self.feedback_text,ft.Divider(),
            ft.Text("❌ Ошибки",weight=ft.FontWeight.BOLD),self.errors_list,ft.Divider(),
            ft.Text("📝 Что потренировать",weight=ft.FontWeight.BOLD),self.tasks_list
        ],spacing=8),padding=18))
        self.loading=ft.ProgressRing(visible=False)
        self.controls=[TopBar("AI Проверка ДЗ"),
            ft.Container(content=ft.Column([
                ft.Text("📸 Загрузите фото выполненной работы",size=20,weight=ft.FontWeight.BOLD),
                self.homework_dropdown,
                ft.Row([ft.ElevatedButton("Загрузить фото",icon=ft.icons.CAMERA_ALT,on_click=lambda e:self.file_picker.pick_files(allow_multiple=False,file_type=ft.FilePickerFileType.IMAGE)),
                        ft.ElevatedButton("Проверить с AI",icon=ft.icons.AUTO_AWESOME,on_click=self.check_homework),
                        self.loading],wrap=True),
                self.image_preview,self.result_card
            ],scroll=ft.ScrollMode.AUTO,spacing=12),padding=15,expand=True)]

    def _load_homeworks(self):
        try:
            res=supabase.get_homeworks(class_name=self.user.class_name)
            self.homework_dropdown.options=[ft.dropdown.Option(h["id"],h.get("topic") or h.get("paragraph") or "Задание") for h in (res.data or [])]
        except Exception as ex: self.page.show_snack_bar(ft.SnackBar(ft.Text(f"Не удалось загрузить ДЗ: {ex}")))

    def on_file_picked(self,e):
        if e.files:
            with open(e.files[0].path,"rb") as f:self.image_bytes=f.read()
            self.image_preview.src_base64=base64.b64encode(self.image_bytes).decode()
            self.image_preview.visible=True; self.page.update()

    async def _check(self,homework_id):
        try:
            hw=(supabase.get_homework(homework_id).data or {})
            subject=(hw.get("subjects") or {}).get("name","")
            task=" ".join(x for x in [hw.get("topic"),hw.get("paragraph"),hw.get("exercise"),hw.get("note")] if x)
            result=await asyncio.to_thread(gemini.check_homework,self.image_bytes,subject,task)
            photo_url=None
            try:
                path=f"{self.user.user_id}/{homework_id}/{uuid.uuid4().hex}.jpg"
                supabase.upload_file("homeworks",path,self.image_bytes)
                photo_url=supabase.get_public_url("homeworks",path)
            except Exception as ex:
                print("Storage:",ex)
            existing=supabase.get_submissions(homework_id=homework_id,student_id=self.user.user_id).data or []
            payload={"photo_url":photo_url,"ai_feedback":result["ai_feedback"],"extra_tasks":result["extra_tasks"],
                     "score":result["score"],"status":"checked","is_completed":True}
            if existing: supabase.update_submission(existing[0]["id"],payload)
            else:
                payload.update({"homework_id":homework_id,"student_id":self.user.user_id})
                supabase.submit_homework(payload)
            self.score_text.value=f"Оценка: {result['score']}/100"
            self.score_text.color=ft.colors.GREEN if result["score"]>=70 else ft.colors.ORANGE if result["score"]>=50 else ft.colors.RED
            self.feedback_text.value=result["ai_feedback"]
            self.errors_list.controls=[ft.Text("• "+x) for x in result["errors_found"]] or [ft.Text("Ошибок не найдено 🎉",color=ft.colors.GREEN)]
            self.tasks_list.controls=[ft.Text(f"{i+1}. {x}") for i,x in enumerate(result["extra_tasks"])] or [ft.Text("Дополнительные задания не нужны.")]
            self.result_card.visible=True
        except Exception as ex:
            self.page.show_snack_bar(ft.SnackBar(ft.Text(f"Ошибка проверки: {ex}")))
        self.loading.visible=False; self.page.update()

    def check_homework(self,e):
        if not self.image_bytes or not self.homework_dropdown.value:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Выберите ДЗ и загрузите фото."))); return
        self.loading.visible=True; self.page.update(); self.page.run_task(self._check,self.homework_dropdown.value)
