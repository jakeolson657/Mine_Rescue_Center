from django.urls import path

from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('new/', views.new_thread, name='new_thread'),
    path('about/<str:kind>/<int:pk>/', views.about, name='about'),
    path('c/<slug:slug>/', views.category, name='category'),
    path('reply/<int:pk>/', views.reply, name='reply'),
    path('follow/<int:pk>/', views.toggle_follow, name='follow'),
    path('t/<int:pk>/', views.thread_detail),
    path('t/<int:pk>/<slug:slug>/', views.thread_detail, name='thread'),
    path('post/<int:pk>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:pk>/answer/', views.mark_answer, name='mark_answer'),
    path('post/<int:pk>/report/', views.report_post, name='report_post'),
    path('post/<int:pk>/moderate/', views.moderate, name='moderate'),
    path('signin/', views.signin_view, name='signin'),
    path('signin/confirm/', views.signin_confirm, name='signin_confirm'),
    path('signout/', views.signout, name='signout'),
    path('profile/', views.profile, name='profile'),
]
