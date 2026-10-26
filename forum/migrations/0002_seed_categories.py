from django.db import migrations

CATEGORIES = [
    ('Rules & Interpretations', 'rules', "How the contest rules apply — ask, argue, and settle on an answer."),
    ('Problem Discussion', 'problems', "Past contest problems: how teams worked them and what judges looked for."),
    ('Written Tests & Benching', 'written-tests', "Written test questions, answer keys, and apparatus benching."),
    ('Training & Techniques', 'training', "Team training, first aid, rope rescue, gas detection, and equipment."),
    ('Contests & Events', 'events', "Upcoming contests, results, travel, and finding teams."),
    ('Site Feedback', 'site-feedback', "Ideas and problems with the Mine Rescue Center site."),
]


def seed(apps, schema_editor):
    Category = apps.get_model('forum', 'Category')
    for order, (name, slug, description) in enumerate(CATEGORIES):
        Category.objects.get_or_create(slug=slug, defaults={
            'name': name, 'description': description, 'sort_order': order,
        })


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
