from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Book, BookCopy, BookRequest, BorrowRecord
from django.contrib.admin import AdminSite
# Add custom CSS
class CustomAdminSite(AdminSite):
    site_header = "📖 Library Management"
    site_title = "Library Dashboard"
    index_title = "Welcome to Your Smart Library"

    def each_context(self, request):
        context = super().each_context(request)
        context['extra_css'] = ['css/admin_custom.css']  # load your CSS
        return context
    
admin_site = CustomAdminSite(name='custom_admin')


# --- Custom User Admin ---
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("id", "username", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("username", "password", "role")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "role", "password1", "password2", "is_staff", "is_active")}
        ),
    )
    search_fields = ("username",)
    ordering = ("id",)


# --- Book Admin ---
class BookAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "isbn", "category", "publisher")
    search_fields = ("title", "author", "isbn", "category")


# --- Book Copy Admin ---
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "accession_no")
    search_fields = ("book__title", "accession_no")


# --- Book Request Admin ---
class BookRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "book_copy", "status", "request_date", "admin_comment")
    list_filter = ("status", "request_date")
    search_fields = ("student_username", "book_copy_accession_no")


# --- Borrow Record Admin ---
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "book_copy", "borrow_date", "return_date", "returned")
    list_filter = ("returned", "borrow_date", "return_date")
    search_fields = ("student_username", "book_copy_accession_no")


# --- Register models ---
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Book, BookAdmin)
admin.site.register(BookCopy, BookCopyAdmin)
admin.site.register(BookRequest, BookRequestAdmin)
admin.site.register(BorrowRecord, BorrowRecordAdmin)