from django.contrib import admin

from studyflow.admin_export import export_as_csv

from .models import Book, BookRating, SavedBook


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'subject', 'level', 'is_postgraduate')
    list_filter = ('level', 'is_postgraduate', 'subject')
    search_fields = ('title', 'author', 'subject')


@admin.register(SavedBook)
class SavedBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'saved_at')
    list_filter = ('user',)


@admin.register(BookRating)
class BookRatingAdmin(admin.ModelAdmin):
    actions = ['export_as_csv']
    export_as_csv = export_as_csv
    list_display = ('book', 'user', 'stars', 'created_at')
    list_filter = ('stars', 'created_at')
    search_fields = ('book__title', 'user__username')
    ordering = ('-created_at',)
