from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('problems/', views.past_problems, name='past_problems'),
    path('problems/quiz/<int:pk>/', views.quiz_detail, name='quiz_detail'),
    path('training/', views.training_resources, name='training_resources'),
    path('updates/', views.updates, name='updates'),
    path('about/', views.about, name='about'),
    path('feedback/', views.feedback, name='feedback'),
    path('calendar/', views.CalendarView.as_view(), name='calendar'),
    path('event/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('event/<int:pk>/calendar.ics', views.event_ics, name='event_ics'),
]
