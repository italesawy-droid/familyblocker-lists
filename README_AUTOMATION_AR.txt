# FamilyBlocker GitHub Lists

الغرض:
إدارة قوائم الحظر الخاصة بإضافة FamilyBlocker مع تصنيف الأفلام حسب كود التصنيف.

## الملفات الأساسية للإضافة

- `blocked_keywords.txt`
- `blocked_titles.txt`

## ملفات الإدارة

- `blocked_titles_manual.txt`
  أسماء تضيفها أنت يدويًا، وتبقى دائمًا في الحظر.
- `blocked_titles_auto.txt`
  يتم توليده تلقائيًا.
- `blocked_titles_by_genre.txt`
  ملف مراجعة مصنف حسب كود التصنيف واسم التصنيف.
- `blocked_titles_sources.tsv`
  جدول يوضح كل فيلم جاء من أي تصنيف.
- `blocked_titles_allowlist.txt`
  أسماء أفلام تريد استثنائها من التحديث التلقائي فقط.
- `blocked_genres_enabled.txt`
  كل التصنيفات المتشددة المفعلة مبدئيًا.
- `blocked_genres_disabled.txt`
  ضع فيه كود أي تصنيف تريد إيقافه بالكامل.

## المنطق

`blocked_titles.txt = blocked_titles_manual.txt + blocked_titles_auto.txt - blocked_titles_allowlist.txt`

مهم:
إذا كان الفيلم موجودًا في `blocked_titles_manual.txt` فلن يتم فتحه بواسطة `allowlist`.
إذا أردت فتح فيلم يدوي، احذفه من `blocked_titles_manual.txt` أيضًا.

## تشغيل يدوي

`Actions → Update blocked titles → Run workflow`

## تعطيل تصنيف كامل

افتح `blocked_genres_disabled.txt` وأضف الكود فقط، مثل:

`Q2991565`

ثم شغّل `Run workflow`.
