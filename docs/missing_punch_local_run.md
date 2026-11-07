# تشغيل مراجعة بصمات الموظف 1723 على الماك (تجريبي)

لا تفلش الـ M5. هذه واجهة محلية مستقلة لا تتصل بجهاز البصمة ولا تغير وقته.

## 1. الحصول على الفرع
```sh
cd "$HOME/zkteco-m5-lab/ZKTeco_set_time"
git fetch origin
git switch --track origin/feature/missing-punch-review
```
إذا كان الفرع موجوداً محلياً مسبقاً، استخدم `git switch feature/missing-punch-review` ثم `git pull --ff-only`.

## 2. تشغيل اختبارات الوحدات
```sh
PYTHONPATH=tools python3 tools/test_missing_punch_review.py
PYTHONPATH=tools python3 tools/test_missing_punch_notes.py
```

## 3. الاستيراد
بعد التأكد من عناوين الأعمدة الفعلية واتجاه IN/OUT في تصدير ZKTime، شغّل:

```sh
PYTHONPATH=tools python3 tools/run_missing_punch_review.py \
  --csv local/export.attendance.csv \
  --employee-id 1723 \
  --employee-column "User ID" \
  --timestamp-column "Date/Time" \
  --direction-column "Punch State" \
  --in-value "Check In" --out-value "Check Out" \
  --workdays "2026-11-03,2026-11-04" \
  --complete-days "2026-11-03,2026-11-04"
```

**الأسماء والقيم والتواريخ أعلاه أمثلة فقط.** لا تستخدمها كما هي قبل فحص التصدير وتأكيد أن الأيام ضمن آخر أربعة أيام مكتملة. يجب تحديد الأيام المكتملة فقط بعد التأكد من أن الملف يحتوي كل حركات تلك الأيام؛ لا تفترض اكتمال التصدير.

## 4. فتح واجهة المراجعة
```sh
PYTHONPATH=tools python3 tools/missing_punch_dashboard.py
```
افتح `http://127.0.0.1:8767/` على الماك. الواجهة لا تعمل من الآيفون حتى نربطها لاحقاً ببوابة HTTPS مع مصادقة مناسبة.

الحذف يزيل الملاحظة المحلية فقط؛ عند إعادة الاستيراد والفحص قد تظهر من جديد. سجلات الجهاز الأصلية لا تتغير. النتائج المعروضة آخر فحص محفوظ، لذلك حذف ملاحظة لا يغيّر صف نتيجة الفحص حتى يُعاد الفحص.

## حدود الإصدار
- يحتاج ملف CSV حقيقياً مع تحديد أسماء الأعمدة وحالات الدخول والخروج.
- يحتاج جدول دوام وعطل موثوقاً.
- لم يتم اختبار الواجهة أو الاستيراد على بيانات جهاز حقيقية.
- لا توجد حتى الآن قراءة مباشرة من ZKTeco أو واجهة على M5.
- ملفات `local/` مستثناة من Git.
