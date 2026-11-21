from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Building, ClinicAnnouncement, Course, Department, Room, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Clinic Connect info', {
            'fields': ('role', 'id_number', 'department', 'course', 'year_block', 'contact_number'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Clinic Connect info', {
            'fields': ('role', 'email', 'id_number', 'department', 'contact_number'),
        }),
    )


class CourseInline(admin.TabularInline):
    model = Course
    extra = 1


class BuildingInline(admin.TabularInline):
    model = Building
    extra = 0


class RoomInline(admin.TabularInline):
    model = Room
    extra = 3
    fields = ('floor', 'room_number', 'room_name')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    inlines = [CourseInline, BuildingInline]


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'total_rooms')
    list_filter = ('department',)
    inlines = [RoomInline]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department')
    list_filter = ('department',)
    search_fields = ('code', 'name')


@admin.register(ClinicAnnouncement)
class ClinicAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'department', 'event_date', 'is_active', 'created_at')
    list_filter = ('audience', 'is_active', 'department')
    search_fields = ('title', 'message')