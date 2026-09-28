from django import template

register = template.Library()


@register.filter
def due_label(task):
    """Human wording for a task's deadline: 'Due tomorrow', 'Overdue by 2 days'..."""
    if task.is_done:
        return 'Done'
    days = task.days_left
    if days < 0:
        n = abs(days)
        return f'Overdue by {n} day' + ('' if n == 1 else 's')
    if days == 0:
        return 'Due today'
    if days == 1:
        return 'Due tomorrow'
    if days <= 7:
        return f'Due in {days} days'
    return f'Due {task.due_date:%d %b}'


@register.filter
def due_state(task):
    """CSS state for the deadline chip."""
    if task.is_done:
        return 'done'
    if task.days_left < 0:
        return 'late'
    if task.days_left <= 2:
        return 'soon'
    return 'ok'
