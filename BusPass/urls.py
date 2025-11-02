from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Registration
    path('register/', views.register, name='register'),

    # Dashboard URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    
    # User URLs
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('routes/', views.view_routes, name='view_routes'),
    path('apply/<int:route_id>/', views.apply_for_pass, name='apply_for_pass'),
    path('payment_success/', views.payment_success, name='payment_success'),
    path('my_pass/', views.my_pass, name='my_pass'),
    path('download_pass/<int:pass_id>/', views.download_buspass, name='download_buspass'),
    path('cancel_pass/<int:pass_id>/', views.cancel_pass, name='cancel_pass'),
    path('support/submit/', views.submit_support_message, name='submit_support_message'),
    path('support/ai/', views.ai_support_chat, name='ai_support_chat'),
    
    # Admin URLs
    path('admin/routes/add/', views.admin_add_route, name='admin_add_route'),
    path('admin/routes/edit/<int:route_id>/', views.admin_edit_route, name='admin_edit_route'),
    path('admin/routes/view/', views.admin_view_routes, name='admin_view_routes'),
    path('admin/passes/', views.admin_view_applications, name='admin_view_applications'),
    path('admin/process_pass/<int:pass_id>/', views.admin_process_pass, name='admin_process_pass'),
]