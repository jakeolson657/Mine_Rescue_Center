import django.db.models.deletion
from django.db import migrations, models


def group_problems_into_competitions(apps, schema_editor):
    """Create a Competition for each existing problem's free-text competition
    name (falling back to the problem title) and link the problem to it."""
    Competition = apps.get_model('pages', 'Competition')
    CompetitionProblem = apps.get_model('pages', 'CompetitionProblem')
    for problem in CompetitionProblem.objects.all():
        name = (problem.legacy_competition or problem.title).strip() or problem.title
        competition, _ = Competition.objects.get_or_create(name=name, year=problem.year)
        problem.competition = competition
        problem.save(update_fields=['competition'])


def ungroup_problems(apps, schema_editor):
    CompetitionProblem = apps.get_model('pages', 'CompetitionProblem')
    for problem in CompetitionProblem.objects.select_related('competition').all():
        if problem.competition_id:
            problem.legacy_competition = problem.competition.name
            problem.year = problem.competition.year
            problem.save(update_fields=['legacy_competition', 'year'])


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0004_competitionproblem_problemdocument_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Competition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='e.g. Loveland, Colorado', max_length=200)),
                ('year', models.PositiveIntegerField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-year', 'name'],
            },
        ),
        migrations.AddField(
            model_name='competitionproblem',
            name='sort_order',
            field=models.PositiveIntegerField(default=0, help_text='Problems are listed lowest number first'),
        ),
        migrations.AddField(
            model_name='problemdocument',
            name='sort_order',
            field=models.PositiveIntegerField(default=0, help_text='Documents are listed lowest number first'),
        ),
        migrations.AlterModelOptions(
            name='competitionproblem',
            options={'ordering': ['sort_order', 'title']},
        ),
        migrations.AlterModelOptions(
            name='problemdocument',
            options={'ordering': ['sort_order', 'title']},
        ),
        migrations.AlterField(
            model_name='competitionproblem',
            name='title',
            field=models.CharField(help_text='e.g. Coal Day 1, Nonmetal Day 2, Bench, First Aid', max_length=200),
        ),
        migrations.RenameField(
            model_name='competitionproblem',
            old_name='competition',
            new_name='legacy_competition',
        ),
        migrations.AddField(
            model_name='competitionproblem',
            name='competition',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='problems', to='pages.competition'),
        ),
        migrations.RunPython(group_problems_into_competitions, ungroup_problems),
        migrations.RemoveField(
            model_name='competitionproblem',
            name='legacy_competition',
        ),
        migrations.RemoveField(
            model_name='competitionproblem',
            name='year',
        ),
        migrations.AlterField(
            model_name='competitionproblem',
            name='competition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='problems', to='pages.competition'),
        ),
    ]
