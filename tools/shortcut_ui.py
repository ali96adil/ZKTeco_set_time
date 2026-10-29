"""Additional mobile shortcut panel; inserted into the Mac HTTPS dashboard."""
import json


def shortcut_panel(csrf: str, enable_write: bool) -> str:
    controls = "" if enable_write else "<p class='note'>التطبيق الفعلي متوقف؛ شغّل السيرفر بـ --enable-write عند الحاجة.</p>"
    return (
        """<section class="card" id="quickPanel">
<h2 style="font-size:18px">اختصارات الساعة المحفوظة</h2>
<p class="small">اضغط الاختصار للتطبيق مباشرة على الجهاز الحقيقي، بدون سلسلة نوافذ تأكيد.
بعد التنفيذ تُقرأ الساعة مرة واحدة للتحقق. التغييرات الأكبر من يوم تحتاج التأكيد اليدوي.</p>
<div id="shortcutList"></div>
<hr>
<h3 style="font-size:16px">إضافة اختصار</h3>
<label for="quickName">اسم الزر</label>
<input id="quickName" maxlength="32" placeholder="مثلاً: بداية الدوام" style="direction:rtl">
<label for="quickKind">نوع الاختصار</label>
<select id="quickKind" style="width:100%;padding:12px;background:#0e1c2c;color:white">
<option value="phone">مزامنة مع الهاتف</option>
<option value="time">وقت فقط (يبقى تاريخ الجهاز)</option>
<option value="date">تاريخ فقط (تبقى ساعة الجهاز)</option>
<option value="datetime">تاريخ ووقت محددان</option>
</select>
<div id="quickValueBox" hidden><label for="quickValue">القيمة</label>
<input id="quickValue" type="time" step="1"></div>
<button type="button" id="shortcutSave" class="primary">حفظ اختصار جديد</button>
<p id="shortcutStatus" class="small"></p>
</section>""" + controls +
        """<script>
(function(){
'use strict';
const csrf = SHORTCUT_CSRF_HERE;
const canWrite = SHORTCUT_CAN_WRITE;
const e=id=>document.getElementById(id);
let items=[],busy=false;
function status(msg){e('shortcutStatus').textContent=msg;}
async function request(path,method,body){
 const r=await fetch(path,{
   method:method,credentials:'same-origin',cache:'no-store',
   headers:method==='POST'?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},
   body:method==='POST'?JSON.stringify(body):undefined
 });
 const j=await r.json();
 if(!r.ok)throw Error(j.error||'فشل الطلب');
 return j;
}
function kindTitle(p){
 if(p.kind==='phone')return 'مزامنة';
 if(p.kind==='time')return 'وقت '+p.value;
 if(p.kind==='date')return 'تاريخ '+p.value;
 return p.value.replace('T',' ');
}
function repaint(){
 const list=e('shortcutList');
 list.replaceChildren();
 for(const p of items){
   const row=document.createElement('div');
   row.style.cssText='display:flex;gap:7px;align-items:center;margin:9px 0';
   const action=document.createElement('button');
   action.type='button';
   action.style.flex='1';
   action.style.textAlign='right';
   action.textContent=p.name+' — '+kindTitle(p);
   action.disabled=!canWrite||busy;
   action.onclick=async()=>{
     if(busy)return;
     busy=true;repaint();status('جاري تطبيق التوقيت وقراءة الجهاز للتحقق...');
     try{
       const r=await request('/api/quick','POST',{id:p.id,client_epoch_ms:Date.now()});
       status(r.status==='VERIFIED'
        ?'تم ضبط ساعة البصمة بنجاح: '+r.requested_time.replace('T',' ')
        :'لم تتأكد النتيجة. تحقق من شاشة الجهاز قبل إعادة المحاولة.');
       measuredOffsetMs=null;measuredAtMs=0;
       e('device').textContent='—';e('delta').textContent='—';
     }catch(err){status('لم يتم تأكيد التعديل: '+err.message);}
     finally{busy=false;repaint();}
   };
   const remove=document.createElement('button');
   remove.type='button';
   remove.textContent='حذف';
   remove.style.cssText='background:#394453';
   remove.disabled=busy || items.length<=1;
   remove.onclick=async()=>{
     const next=items.filter(q=>q.id!==p.id);
     try{
       await request('/api/shortcuts','POST',{items:next});
       items=next;repaint();status('تم حذف الاختصار.');
     }catch(err){status(err.message);}
   };
   row.append(action,remove);
   list.append(row);
 }
}
function updateField(){
 const kind=e('quickKind').value;
 e('quickValueBox').hidden=kind==='phone';
 e('quickValue').type=kind==='time'?'time':kind==='date'?'date':'datetime-local';
 e('quickValue').step=1;
 e('quickValue').value='';
}
e('quickKind').onchange=updateField;
e('shortcutSave').onclick=async()=>{
 try{
   if(items.length>=12)throw Error('الحد الأعلى 12 اختصاراً');
   let name=e('quickName').value.trim();
   if(!name)throw Error('أدخل اسم الاختصار');
   const kind=e('quickKind').value;
   let value=kind==='phone'?'':e('quickValue').value;
   if(kind==='datetime'&&value.length===16)value+=':00';
   if(kind==='time'&&value.length===5)value+=':00';
   if(kind!=='phone'&&!value)throw Error('أدخل قيمة صحيحة');
   const id='p'+Date.now().toString(36);
   const next=[...items,{id,name,kind,value}];
   await request('/api/shortcuts','POST',{items:next});
   items=next;repaint();e('quickName').value='';updateField();
   status('تم حفظ الاختصار على الماك.');
 }catch(err){status(err.message);}
};
updateField();
request('/api/shortcuts','GET').then(j=>{items=j.items;repaint();})
 .catch(err=>status('تعذر تحميل الاختصارات: '+err.message));
})();
</script>"""
    ).replace("SHORTCUT_CSRF_HERE", json.dumps(csrf)).replace(
        "SHORTCUT_CAN_WRITE", "true" if enable_write else "false"
    )
