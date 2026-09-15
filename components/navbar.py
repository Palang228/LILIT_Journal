"""Нижняя навигация."""
import flet as ft
from models.user import app_state

class BottomNavBar(ft.Container):
    def __init__(self,page,on_navigate,active_tab="schedule"):
        self.on_navigate=on_navigate
        role=app_state.current_user.role if app_state.current_user else "student"
        items=[("ai_tutor",ft.icons.PSYCHOLOGY),("schedule",ft.icons.CALENDAR_TODAY),("profile",ft.icons.PERSON)]
        if role=="teacher": items=[("teacher",ft.icons.GROUP),("schedule",ft.icons.CALENDAR_TODAY),("profile",ft.icons.PERSON)]
        if role=="parent": items=[("home",ft.icons.HOME),("grades",ft.icons.GRADE),("profile",ft.icons.PERSON)]
        buttons=[]
        for key,icon in items:
            active=key==active_tab
            buttons.append(ft.Container(content=ft.Icon(icon,color=ft.colors.ON_PRIMARY if active else ft.colors.ON_SURFACE_VARIANT,size=27),
                width=52,height=52,border_radius=26,bgcolor=ft.colors.PRIMARY_CONTAINER if active else None,
                alignment=ft.alignment.center,on_click=lambda e,k=key:self.on_navigate(k)))
        super().__init__(content=ft.Row(buttons,alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                         padding=ft.padding.symmetric(vertical=10),bgcolor=ft.colors.SURFACE,
                         border_radius=ft.border_radius.only(top_left=24,top_right=24))
