from django.contrib import admin

from .models import Book, SavedBook


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'subject', 'level', 'is_postgraduate')
    list_filter = ('level', 'is_postgraduate', 'subject')
    search_fields = ('title', 'author', 'subject')


@admin.register(SavedBook)
class SavedBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'saved_at')
    list_filter = ('user',)
