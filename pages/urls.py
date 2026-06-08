from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('calendar/', views.CalendarView.as_view(), name='calendar'),
    path('event/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('event/new/', views.EventCreateView.as_view(), name='event_create'),
    path('event/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_update'),
    path('event/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
]
