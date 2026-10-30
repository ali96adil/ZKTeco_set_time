#pragma once
// Single-page mobile interface: instant tabs (no page-to-page network round trips).
// Does not expose any HTTP terminal clock write or staff record operation.
#include <Arduino.h>
static const char M9_HOME[] PROGMEM = R"M9HTML(<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0c1725">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="ZK Clock">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<title>ZK Clock</title>
<style>
:root{color-scheme:dark;font:15px system-ui,-apple-system,Tahoma,Arial,sans-serif}
*{box-sizing:border-box}
body{background:#0c1725;color:#f3f7ff;margin:0;line-height:1.5}
.wrap{max-width:590px;padding:16px 14px 28px;margin:0 auto}
.top{display:flex;align-items:center;justify-content:space-between;margin:0 0 14px}
h1{font-size:23px;letter-spacing:-.5px;margin:0}h2{font-size:18px;margin:0 0 12px}
sub,small,.muted{font-size:12px;color:#aebdd0}
.card{background:#17283c;border:1px solid #294157;border-radius:16px;padding:16px;margin-bottom:12px}
.tabbar{position:sticky;top:0;display:flex;gap:5px;padding:8px 0 12px;background:#0c1725;z-index:4}
.tabbar button{background:#1c3045;flex:1;padding:11px 4px;font-size:13px}
.tabbar button.active{background:#2d75b6}
button{border:0;border-radius:10px;background:#2979b8;color:white;padding:12px;font:inherit;font-weight:650;cursor:pointer}
button:disabled{opacity:.55;cursor:not-allowed}
button.alt{background:#334962}
.action{width:100%;margin-top:10px}
.row{display:flex;align-items:center;justify-content:space-between;gap:9px}
.row>*{min-width:0}.row button{white-space:nowrap}
.preset{padding:11px 0;border-bottom:1px solid #2e4459}.preset:last-child{border:0}
.when{direction:ltr;text-align:right;font-variant-numeric:tabular-nums;color:#b6daff;font-size:14px}
.bigtime{font-size:25px;direction:ltr;text-align:right;font-variant-numeric:tabular-nums}
.status{font-size:12px;padding:6px 10px;border-radius:30px;background:#29475b;color:#b5e6f6}
.note{color:#b5c7d9;font-size:13px;margin:8px 0}
.warn{color:#ffd08a;font-size:13px}
.ok{color:#8be5b9;font-size:13px}
label{display:block;color:#c2d2e5;font-size:13px;margin:12px 0 5px}
input,select,textarea{width:100%;border:1px solid #426380;background:#0d1e2e;color:white;border-radius:9px;padding:12px;font:inherit}
fieldset{border:1px solid #365169;border-radius:12px;margin:10px 0;padding:11px}
fieldset .row{align-items:flex-end}fieldset button{padding:10px;background:#414d62}
footer{color:#7e93a9;font-size:11px;padding:12px 0}
[hidden]{display:none!important}
</style></head><body>
<div class="wrap">
<header class="top"><div><small>ZKTeco / M5StickC Plus</small><h1>التحكم بالساعة</h1></div><div><span class="status" id="batteryTop">بطارية —</span><br><small id="modeState">ZK CLOCK</small></div></header>
<nav class="tabbar" aria-label="الصفحات">
<button data-tab="home" class="active">الرئيسية</button>
<button data-tab="presets">الأوامر</button>
<button data-tab="settings">الإعدادات</button>
<button data-tab="rtc">RTC</button>
</nav>
<section id="home">
<div class="card">
<div class="row"><h2>ساعة البصمة</h2><button id="clockRead" class="alt">قراءة</button></div>
<div id="deviceClock" class="bigtime">—</div>
<p id="clockStatus" class="note">قراءة مباشرة عند الضغط فقط</p>
</div>
<div class="card">
<div class="row"><h2>الأوامر السريعة</h2><small id="count">—</small></div>
<div id="homePresets"><p class="note">جاري تحميل الأوامر…</p></div>
<p class="note">لمسة واحدة تنفّذ الأمر مباشرة، بما فيه فرق أكبر من 24 ساعة. بعدها النظام يتحقق من ساعة البصمة تلقائياً، بدون إعادة إرسال الأمر.</p>
</div>
<div class="card">
<div class="row"><div><h2>تسجيل الدخول</h2><p class="note">الدخول محفوظ على الآيفون ويتجدد تلقائياً</p></div>
<span class="status" id="armedHome">مقفول</span></div>
<button class="alt action" id="refreshHome">تحديث الحالة</button>
<button class="alt action" id="revokeAll">خروج من كل الأجهزة</button>
</div>
</section>
<section id="presets" hidden>
<div class="card">
<div class="row"><h2>تعديل الاختصارات</h2><button id="addPreset">+ إضافة</button></div>
<p class="note">كل اختصار تاريخ ووقت كامل. الحفظ متاح من الآيفون المسجل دخول عبر HTTPS.</p>
<div id="presetEditor"></div>
<button class="action" id="savePresets">حفظ الأوامر</button>
</div>
</section>
<section id="settings" hidden>
<div class="card">
<h2>الاتصال والجهاز</h2>
<div class="row"><span class="muted">شبكة الاتصال</span><b id="sta">—</b></div>
<div class="row"><span class="muted">عنوان البصمة</span><b id="zkip" dir="ltr">—</b></div>
<div class="row"><span class="muted">الجلسة</span><b id="armedSettings">مقفول</b></div>
<div class="row"><span class="muted">بطارية M5 (تقريبية)</span><b id="batteryDetail">—</b></div>
<p class="note">النسبة تقدير من فولتية AXP192؛ الفولتية أدق. ظهور USB يعني الكهرباء متصلة وليس بالضرورة البطارية تشحن.</p>
<label for="apName">اسم شبكة إعداد M5</label>
<input id="apName" maxlength="24" autocomplete="off" placeholder="ZK-Setup">
<label for="idle">إطفاء إضاءة الشاشة بعد</label>
<select id="idle">
<option value="15">15 ثانية</option><option value="30">30 ثانية</option>
<option value="60">دقيقة</option><option value="120">دقيقتين</option>
<option value="0">بدون نوم</option>
</select>
<button class="action" id="saveSettings">حفظ الاسم والنوم</button>
<p class="note">اسم شبكة الإعداد يتفعّل عند دخول SETUP مرة ثانية. لتغيير Wi-Fi أو حساب الجهاز، اختار A — SETUP على الـM5 واتصل بشبكته؛ افتح نفس العنوان https://zkclock.local.</p>
<p class="note">رابط الإعدادات في وضع SETUP: https://zkclock.local/setup. البديل إذا mDNS غير متوفر: https://192.168.4.1/setup.</p>
</div>
</section>
<section id="rtc" hidden>
<div class="card"><h2>ساعة M5 الداخلية</h2>
<div id="rtcClock" class="bigtime">—</div>
<p id="rtcState" class="note">—</p>
<button class="action" id="syncRtc">مزامنة ساعة M5 من الآيفون</button>
<p class="note">مزامنة ساعة M5 فقط، وليس ساعة البصمة.</p>
<p class="note">عمر المعايرة المقبول 7 أيام. المزامنة من الزر أعلاه.</p>
</div>
</section>
<p id="message" aria-live="polite" class="note"></p>
<footer>HTTPS على M5 • التنفيذ الحقيقي محصور بإصدار الكتابة المؤهل</footer>
</div>
<script>
'use strict';
const el=id=>document.getElementById(id);
let state=null,editor=[],busy=false,activeTab='home';
function message(t,good=false){el('message').textContent=t;el('message').className=good?'ok':'warn';}
function showTab(id){
 activeTab=id;
 for(const name of ['home','presets','settings','rtc'])el(name).hidden=name!==id;
 document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));
}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
async function api(path,method='GET',fields=null){
 const res=await fetch(path,{method,cache:'no-store',credentials:'same-origin',
 headers:method==='POST'?{'Content-Type':'application/x-www-form-urlencoded','X-ZK-CSRF':state?.csrf||''}:{},
 body:method==='POST'?new URLSearchParams(fields):undefined});
 const text=await res.text();let result={};
 try{result=JSON.parse(text);}catch(e){result={error:text.slice(0,150)};}
 if(res.status===401){location.replace('/login');throw Error('انتهت جلسة الدخول');}
 if(!res.ok||!result.ok)throw Error(result.error||'فشل الطلب');
 return result;
}
function make(tag,cls,text){const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x;}
function drawHome(){
 const host=el('homePresets');host.replaceChildren();
 if(!state)return;
 const items=state.items||[];
 el('count').textContent=items.length+' محفوظ';
 for(let i=0;i<=items.length;i++){
   const p=i===items.length?{name:'مزامنة من ساعة M5',datetime:state.rtc_time||'RTC'}:items[i];
   const wrap=make('div','preset');
   const title=make('strong','',p.name);
   const row=make('div','row');
   const info=make('div');
   info.append(title,make('div','when',(p.datetime||'').replace('T',' ')));
   const btn=make('button','alt','تنفيذ');
   btn.onclick=async()=>{
     if(busy)return;
     if(!state.write_enabled)return message('التنفيذ مو متاح بهالنسخة');
     busy=true;btn.disabled=true;btn.textContent='جاري التنفيذ…';
     message('جاري إرسال '+p.name+' والتحقق من ساعة البصمة…');
     try{
       // One tap = one authenticated POST = one clock SET_TIME attempt.
       // No browser confirm, no greater-than-24h server confirmation.
       const r=await api('/api/m9/run','POST',{index:String(i)});
       message(r.message||'تم إرسال الأمر وفحص ساعة البصمة',r.verified===true);
     }catch(err){message(err.message);}
     finally{busy=false;btn.disabled=false;btn.textContent='تنفيذ';}
   };
   row.append(info,btn);wrap.append(row);host.append(wrap);
 }
 el('armedHome').textContent=state.authenticated?'موثوقة':'غير موثوقة';
 el('armedSettings').textContent=state.authenticated?'مستمرة':'غير مسجلة';
}
function drawEditor(){
 const host=el('presetEditor');host.replaceChildren();
 editor.forEach((p,i)=>{
   const field=make('fieldset');
   const title=make('div','row');title.append(make('strong','',String(i+1)+'. أمر'));
   const remove=make('button','','حذف');
   remove.type='button';remove.onclick=()=>{editor.splice(i,1);drawEditor();};
   title.append(remove);field.append(title);
   const n=make('label','', 'اسم الاختصار');
   const inp=make('input');inp.value=p.name;inp.maxLength=24;
   inp.oninput=()=>p.name=inp.value;
   const d=make('label','','التاريخ والوقت');
   const when=make('input');when.type='datetime-local';when.step=1;
   when.value=p.datetime;when.oninput=()=>p.datetime=when.value;
   field.append(n,inp,d,when);host.append(field);
 });
}
async function refreshBattery(){
 try{
   const b=await api('/api/battery');
   const suffix=b.usb_power?' · USB':'';
   el('batteryTop').textContent=b.valid?'بطارية ~'+b.percent_estimate+'%'+suffix:'بطارية —';
   el('batteryDetail').textContent=b.valid?'~'+b.percent_estimate+'% · '+Number(b.voltage_v).toFixed(2)+'V'+suffix:'قراءة غير متاحة';
 }catch(e){
   el('batteryTop').textContent='بطارية —';
   el('batteryDetail').textContent='قراءة غير متاحة';
 }
}
async function refresh(){
 try{
   state=await api('/api/m9');
   el('modeState').textContent=state.write_enabled?'تحكم فعّال':'وضع تشخيص';
   editor=(state.items||[]).map(x=>({name:x.name,datetime:x.datetime}));
   el('sta').textContent=state.ssid||'غير محددة';
   el('zkip').textContent=state.zk_ip;
   el('apName').value=state.ap_name;
   el('idle').value=String(state.idle);
   el('rtcClock').textContent=state.rtc_time||'—';
   el('rtcState').textContent=state.rtc_ready?'معايرة صالحة':'تحتاج معايرة';
   drawHome();drawEditor();
   await refreshBattery();
 }catch(err){message('تعذر تحميل البيانات: '+err.message);}
}
el('refreshHome').onclick=refresh;
el('revokeAll').onclick=async()=>{
 if(!confirm('إلغاء كل الجلسات على الأجهزة المسجلة؟'))return;
 try{await api('/api/m9/revoke','POST',{});location.replace('/login');}
 catch(e){message(e.message);}
};
el('syncRtc').onclick=async()=>{
 try{
   const parts=new Intl.DateTimeFormat('en-GB',{
     timeZone:'Asia/Baghdad',year:'numeric',month:'2-digit',day:'2-digit',
     hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'
   }).formatToParts(new Date());
   const d=Object.fromEntries(parts.filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
   const value=d.year+'-'+d.month+'-'+d.day+'T'+d.hour+':'+d.minute+':'+d.second;
   const r=await api('/api/m9/rtc','POST',{datetime:value});
   message(r.message,true);await refresh();
 }catch(e){message(e.message);}
};

el('addPreset').onclick=()=>{
 if(editor.length>=8)return message('الحد الأعلى 8 أوامر');
 editor.push({name:'',datetime:''});drawEditor();
};
el('savePresets').onclick=async()=>{
 const payload={action:'presets'};
 for(let i=0;i<8;i++){
   payload['n'+i]=editor[i]?.name?.trim()||'';
   payload['v'+i]=editor[i]?.datetime||'';
 }
 try{const r=await api('/api/m9/save','POST',payload);message(r.message,true);await refresh();}
 catch(err){message(err.message);}
};
el('saveSettings').onclick=async()=>{
 try{
   const r=await api('/api/m9/save','POST',
        {action:'settings',apname:el('apName').value,idle:el('idle').value});
   message(r.message,true);await refresh();
 }catch(err){message(err.message);}
};
el('clockRead').onclick=async()=>{
 el('clockStatus').textContent='جاري الاتصال بالبصمة…';
 try{
   const r=await api('/api/m9/read');
   el('deviceClock').textContent=r.device_time.replace('T',' ');
   el('clockStatus').textContent='تمت القراءة';
 }catch(err){el('clockStatus').textContent='تعذرت القراءة: '+err.message;}
};
refresh();
setInterval(refreshBattery,30000);
</script></body></html>)M9HTML";
