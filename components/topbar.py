"""Универсальная верхняя панель без Flet AppBar."""
import flet as ft


def TopBar(title, leading=None, actions=None):
    actions = actions or []
    left = []
    if leading is not None:
        left.append(leading)
    left.append(ft.Text(title, size=20, weight=ft.FontWeight.BOLD, expand=True))
    return ft.Container(
        content=ft.Row(left + actions, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )
