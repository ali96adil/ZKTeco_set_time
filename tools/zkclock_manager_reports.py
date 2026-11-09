"""ZK CLOCK Manager v0.3: local, non-mutating employee and calendar views.

No hardware commands, no database writes, no inferred biometric verifications.
Any morning/evening observation is an interpretation of timestamps, not an
attendance decision, and a day with no events is not classified as an absence.
"""
import calendar
from datetime import date, datetime, time, timedelta
import html
import re
from urllib.parse import urlencode

WEEKEND_DAYS = frozenset((4, 5))  # Friday / Saturday; Python: Mon=0
STAMP_FORMAT = '%Y-%m-%d %H:%M:%S'


def validate_employee_id(value):
    value = str(value)
    if not re.fullmatch(r'[0-9]{1,32}', value):
        raise ValueError('Employee ID must contain digits only')
    return value


def validate_hhmm(value):
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
        raise ValueError('Expected time HH:MM')
    return time.fromisoformat(value)


def validate_month(value):
    if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', value):
        raise ValueError('Expected month YYYY-MM')
    return value


def employee_directory(db, *, limit=100, search=''):
    """Names and summarized device records; no additions or corrections."""
    if search and not re.fullmatch(r'[0-9A-Za-z\u0600-\u06FF .-]{1,120}', search):
        raise ValueError('Invalid name/ID search')
    limit = max(1, min(int(limit), 200))
    pattern = '%' + search + '%'
    return [dict(row) for row in db.execute('''
        SELECT d.user_id, COALESCE(u.display_name,'') AS display_name,
               COUNT(p.source_key) AS total_punches,
               MIN(p.occurred) AS first_punch, MAX(p.occurred) AS last_punch
        FROM (SELECT user_id FROM device_users UNION SELECT user_id FROM device_punches) d
        LEFT JOIN device_users u ON u.user_id=d.user_id
        LEFT JOIN device_punches p ON p.user_id=d.user_id
        WHERE (?='' OR d.user_id LIKE ? OR u.display_name LIKE ?)
        GROUP BY d.user_id
        ORDER BY last_punch DESC, d.user_id
        LIMIT ?''', (search, pattern, pattern, limit))]


def employee_month(db, employee_id, *, month=None, morning='08:30',
                   evening='14:45', today=None):
    """Review day-by-day observed movement for a single employee.

    Not an attendance certification: raw punch status/verification semantics have
    not been confirmed for all employees. Do not infer IN/OUT from these labels.
    """
    employee_id = validate_employee_id(employee_id)
    morning_time = validate_hhmm(morning)
    evening_time = validate_hhmm(evening)
    if morning_time >= evening_time:
        raise ValueError('Morning threshold must be before evening threshold')
    person = db.execute('''SELECT display_name FROM device_users
                           WHERE user_id=?''', (employee_id,)).fetchone()
    latest = db.execute('''SELECT MAX(occurred) AS stamp FROM device_punches
                           WHERE user_id=?''', (employee_id,)).fetchone()['stamp']
    if not month:
        month = latest[:7] if latest else (today or date.today()).strftime('%Y-%m')
    month = validate_month(month)
    year, number = map(int, month.split('-'))
    start = date(year, number, 1)
    end = date(year, number, calendar.monthrange(year, number)[1])
    limit_today = today or date.today()
    raw = db.execute('''SELECT occurred, punch, status, occurrence FROM device_punches
         WHERE user_id=? AND occurred>=? AND occurred<=? ORDER BY occurred''',
        (employee_id, start.isoformat() + ' 00:00:00', end.isoformat() + ' 23:59:59'))
    by_day = {}
    for event in raw:
        stamp = datetime.strptime(event['occurred'], STAMP_FORMAT)
        by_day.setdefault(stamp.date(), []).append(stamp)

    counts = {'days_with_events': 0, 'morning_and_evening': 0,
              'morning_only': 0, 'evening_only': 0, 'uncategorized': 0,
              'no_events': 0, 'weekend_days': 0, 'workdays_elapsed': 0}
    results = []
    day = start
    while day <= end:
        stamps = by_day.get(day, [])
        weekend = day.weekday() in WEEKEND_DAYS
        elapsed = day <= limit_today
        first = stamps[0].strftime('%H:%M:%S') if stamps else None
        last = stamps[-1].strftime('%H:%M:%S') if stamps else None
        morning_observed = any(t.time() <= morning_time for t in stamps)
        evening_observed = any(t.time() >= evening_time for t in stamps)
        near = sum(0 <= (right - left).total_seconds() <= 10
                   for left, right in zip(stamps, stamps[1:]))
        if weekend:
            classification = 'weekend_with_events' if stamps else 'weekend'
            counts['weekend_days'] += 1
        elif not elapsed:
            classification = 'future'
        elif not stamps:
            classification = 'no_events'
            counts['no_events'] += 1
        elif morning_observed and evening_observed:
            classification = 'morning_and_evening'
            counts['morning_and_evening'] += 1
        elif morning_observed:
            classification = 'morning_only'
            counts['morning_only'] += 1
        elif evening_observed:
            classification = 'evening_only'
            counts['evening_only'] += 1
        else:
            classification = 'uncategorized'
            counts['uncategorized'] += 1
        if not weekend and elapsed:
            counts['workdays_elapsed'] += 1
        if stamps:
            counts['days_with_events'] += 1
        results.append({'date': day.isoformat(), 'weekday': day.weekday(),
                        'classification': classification, 'count': len(stamps),
                        'first': first, 'last': last, 'near_repeats': near,
                        'morning_observed': morning_observed,
                        'evening_observed': evening_observed})
        day += timedelta(days=1)
    return {'employee_id': employee_id,
            'display_name': person['display_name'] if person else '',
            'month': month, 'morning': morning, 'evening': evening,
            'raw_total': sum(r['count'] for r in results),
            'days': results, 'totals': counts,
            'disclaimer': 'تصنيف استرشادي بحسب وقت الحركات فقط. لا يثبت حضوراً أو انصرافاً أو غياباً.'}


def _h(value):
    return html.escape(str(value), quote=True)


CLASSIFICATIONS = {
    'weekend_with_events': 'عطلة أسبوعية — توجد حركات',
    'weekend': 'عطلة أسبوعية',
    'future': 'لم يأتِ موعد اليوم',
    'no_events': 'لا توجد حركات (ليس إثبات غياب)',
    'morning_and_evening': 'حركات صباحية ومسائية',
    'morning_only': 'حركات صباحية فقط',
    'evening_only': 'حركات مسائية فقط',
    'uncategorized': 'حركات خارج النطاقين',
}

PAGE_CSS = '''
:root{color-scheme:dark;font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
*{box-sizing:border-box}body{background:#0d1420;color:#ecf3fe;margin:0;line-height:1.6}
main{max-width:1050px;margin:auto;padding:22px 13px}h1{margin:7px 0;font-size:1.7rem}
h2{font-size:1.1rem;margin:0 0 13px}p,small{color:#b8c6d8}
section{padding:18px;background:#18283c;border:1px solid #30435b;border-radius:14px;margin:15px 0}
a{color:#a6ccff;text-underline-offset:3px}nav{display:flex;gap:16px;flex-wrap:wrap}
form{display:flex;gap:10px;align-items:end;flex-wrap:wrap}label{display:flex;flex-direction:column;gap:5px;flex:1 1 135px}
input,button{min-height:40px;padding:8px 12px;border-radius:9px;font:inherit;color:#fff;border:1px solid #56708a;background:#102038}
button{cursor:pointer;background:#345b90}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse}
th,td{text-align:right;padding:9px 11px;white-space:nowrap;border-bottom:1px solid #334760}th{color:#b5c9e2}
.numbers{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.num{background:#20364f;border-radius:10px;padding:10px}.num b{display:block;font-size:1.45rem}
.note{padding:12px;border-right:3px solid #bca468;background:#283044;border-radius:5px}
@media(max-width:640px){main{padding:12px}section{padding:12px}table{font-size:.85rem}th,td{padding:7px}input,button{width:100%}}
'''


def render_employee_page(report):
    uid = report['employee_id']
    label = report['display_name'] or ('ID ' + uid)
    rows = ''.join('''<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>
        <td>{}</td><td>{}</td></tr>'''.format(
        _h(row['date']), _h(CLASSIFICATIONS[row['classification']]),
        _h(row['first'] or '—'), _h(row['last'] or '—'),
        _h(row['count']), _h(row['near_repeats'])) for row in report['days'])
    counters = [(title, report['totals'][key]) for title, key in (
        ('أيام فيها حركات', 'days_with_events'),
        ('صباحية ومسائية', 'morning_and_evening'),
        ('صباحية فقط', 'morning_only'),
        ('مسائية فقط', 'evening_only'),
        ('أيام بدون حركات', 'no_events'),
        ('عطل الجمعة والسبت', 'weekend_days'))]
    boxes = ''.join('<div class="num"><small>{}</small><b>{}</b></div>'.format(
        _h(title), value) for title, value in counters)
    return '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ملف الموظف {uid}</title>
<style>{css}</style></head><body><main><nav><a href="/">الرئيسية</a><a href="/employees">الموظفون</a></nav>
<h1>ملف الموظف: {name}</h1><p>رقم الموظف: {uid} · عرض شهري من أرشيف جهاز ZKTeco</p>
<section><h2>اختيار شهر وقواعد العرض</h2><form method="get" action="/employee">
<input type="hidden" name="user" value="{uid}">
<label>الشهر<input type="month" name="month" required value="{month}"></label>
<label>آخر وقت للحركات الصباحية<input type="time" name="morning" value="{morning}"></label>
<label>أول وقت للحركات المسائية<input type="time" name="evening" value="{evening}"></label>
<button type="submit">تطبيق على العرض</button></form>
<p class="note">هذه القواعد تغيّر طريقة العرض فقط، ولا تحفظ تصحيحات أو تعدّل الجهاز.
الجمعة والسبت عطلة افتراضياً؛ اليوم الذي لا يحتوي بصمات ليس دليلاً على الغياب.
التمييز هنا بالتوقيت فقط، وليس توثيقاً لطريقة التحقق البيومتري.</p></section>
<section><h2>ملخص {month}</h2><div class="numbers">{boxes}</div></section>
<section><h2>تفاصيل الأيام</h2><div class="scroll"><table>
<tr><th>التاريخ</th><th>الملاحظة الاسترشادية</th><th>أول حركة</th><th>آخر حركة</th>
<th>عدد الحركات</th><th>متقاربة ≤10 ثوانٍ</th></tr>{rows}</table></div></section>
<p>السجلات الأصلية لا تتغير. لم يتم إنشاء بصمات أو تصحيحات محلية.</p>
</main></body></html>'''.format(css=PAGE_CSS, uid=_h(uid), name=_h(label),
    month=_h(report['month']), morning=_h(report['morning']), evening=_h(report['evening']),
    boxes=boxes, rows=rows)


def render_directory_page(users, *, search=''):
    rows = ''.join('''<tr><td><a href="/employee?{}">{}</a></td><td>{}</td><td>{}</td><td>{}</td></tr>'''.format(
        urlencode({'user': r['user_id']}), _h(r['user_id']),
        _h(r['display_name'] or '—'), r['total_punches'],
        _h(r['last_punch'] or '—')) for r in users)
    return '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>الموظفون — ZK CLOCK</title>
<style>{css}</style></head><body><main><nav><a href="/">الرئيسية</a></nav><h1>دليل الموظفين</h1>
<section><form method="get" action="/employees"><label>الاسم أو الرقم
<input name="search" value="{search}" placeholder="1733"></label><button>بحث</button></form></section>
<section><div class="scroll"><table><tr><th>ID</th><th>الاسم</th><th>عدد الحركات</th><th>آخر حركة</th></tr>{rows}</table></div></section>
<p>البيانات من الجهاز فقط. فتح صفحة الموظف لا يغير السجلات.</p></main></body></html>'''.format(
        css=PAGE_CSS, search=_h(search), rows=rows or '<tr><td colspan="4">لا توجد نتائج</td></tr>')
