exec(open('prep.py').read())
import csv
# sanity: monotonic timestamps by EventIndex
assert (df.groupby('ProcessInstanceId').ts.diff().dropna()>=pd.Timedelta(0)).all()
rows=[]
def add(pid,typ,expl): rows.append((pid,typ,expl))
tk=tasks[tasks._merge=='both'].merge(info[['rt']],left_on='ProcessInstanceId',right_index=True)
ordr=df[df.EventType=='task_completed'].copy(); ordr['a']=ordr.ActivityName.map(short)
seq=ordr.groupby('ProcessInstanceId').a.agg(list)
ACC={'standard':'обычную','urgent':'срочную','contract':'договорную'}
T={'standard':'обычной','urgent':'срочной','contract':'договорной'}
def uname(u): return u[:8]
# 1 skipped manager / wrong order / duplicate check
for pid,s in seq.items():
    rt=info.at[pid,'rt']; r=info.at[pid,'route']
    if 'MGR' not in s and 'BUD' in s:
        add(pid,'Пропуск согласования руководителем',f'В {T[rt]} заявке после проверки (CHK) сразу выполнено «Согласование бюджета», задания «Согласование руководителем» нет вообще; маршрут: {r}. Обязательный этап руководителя пропущен.')
    if 'EXE' in s and 'BUD' in s and s.index('EXE')<s.index('BUD'):
        add(pid,'Нарушение порядка этапов',f'Исполнение заявки (EXE) выполнено раньше согласования бюджета (BUD) в {T[rt]} заявке; порядок закрытия: {" → ".join(s)}. Бюджет проверен уже после исполнения.')
    for i in range(1,len(s)):
        if s[i]=='CHK' and s[i-1]=='CHK':
            add(pid,'Повторная проверка без возврата',f'Задание «Проверка заявки» выполнено дважды подряд (CHK → CHK) без возврата руководителем и доработки; порядок: {" → ".join(s)}. Для обычных заявок повторная проверка бывает только после доработки.'); break
# AUD
for pid,s in seq.items():
    if 'AUD' in s:
        n=s.count('AUD'); rt=info.at[pid,'rt']
        add(pid,'Внеплановая проверка (auditor)',f'В {T[rt]} заявке {n} задания «Внеплановая проверка» ролью auditor между руководителем и бюджетом/юристом/исполнением (маршрут: {" → ".join(s)}). Этап не входит в базовую схему (встречается в 8 из 1000 процессов), оправданность по данным не определить — нужна ручная проверка.')
# loops
rew=tasks[tasks.act=='REW'].groupby('ProcessInstanceId').size()
for pid,n in rew[rew>=3].items():
    rt=info.at[pid,'rt']; res={'END:ful':'исполнена','END:rej':'отклонена'}.get(info.at[pid,'route'].split()[-1],'не завершена')
    add(pid,'Чрезмерное число возвратов на доработку',f'Руководитель возвращал {ACC[rt]} заявку на доработку {n} раз(а) подряд (типично — 0 или 1 раз: 119 процессов с одним возвратом, ≥3 только у 8 процессов); итог процесса: {res}. Цикл доработки аномально длинный.')
# role mismatch
mg=tk[(tk.act=='MGR')&(tk.Role=='requester')]
st=df[df.EventType=='process_started'].set_index('ProcessInstanceId').UserId
for _,r in mg.iterrows():
    self_=st[r.ProcessInstanceId]==r.UserId
    if self_:
        add(r.ProcessInstanceId,'Самосогласование заявки',f'Задание «Согласование руководителем» закрыто пользователем {uname(r.UserId)} с ролью requester (должен быть manager), и это тот же пользователь, что создал заявку: заявитель сам принял решение ({r.Result}).')
    else:
        add(r.ProcessInstanceId,'Согласование не руководителем',f'Задание «Согласование руководителем» закрыто пользователем {uname(r.UserId)} с ролью requester вместо manager (результат: {r.Result}); в остальных {1141} закрытиях этого этапа роль всегда manager.')
# stuck
op=tasks[tasks._merge=='left_only']
cut=pd.Timestamp('2026-07-01 00:00',tz='Etc/GMT-3')
for _,r in op.iterrows():
    days=(cut-r.t_cr).days
    if r.act=='MGR':
        add(r.ProcessInstanceId,'Зависшее согласование руководителем',f'Задание «Согласование руководителем» создано {r.t_cr:%d.%m.%Y %H:%M} и не закрыто на срез 01.07.2026 ({days} дней в ожидании); типичная календарная длительность этапа — медиана ~2 ч, максимум 69 ч среди закрытых. Процесс остановился.')
# slow check
ch=tk[tk.act=='CHK']
for _,r in ch[ch.work_h>=59].iterrows():
    add(r.ProcessInstanceId,'Аномально долгая проверка заявки',f'Задание «Проверка заявки» (тип заявки: {r.rt}) выполнялось {r.cal_h:.0f} календарных ч = {r.work_h:.0f} рабочих ч; медиана этапа ~0,4 рабочих часа, 99-й перцентиль ~8 ч. Это ~{r.cal_h/24:.0f} суток ожидания.')
for _,r in ch[(ch.work_h>=7.9)&(ch.work_h<9)].iterrows():
    add(r.ProcessInstanceId,'Долгая проверка заявки',f'Задание «Проверка заявки» (тип заявки: {r.rt}) заняло {r.work_h:.0f} рабочих ч ({r.cal_h:.0f} календарных) при медиане ~0,4 ч; почти целый рабочий день, на порядок выше обычного (Q3+3·IQR ≈ 1,4 ч).')
# ultra-fast
tk['sec']=tk.cal_h*3600
fp=tk[tk.sec<=60].groupby('ProcessInstanceId')
for pid,g in fp:
    rt=g.rt.iloc[0]; acts=','.join(sorted(g.act))
    add(pid,'Сверхбыстрые задания (формальное закрытие)',f'Все {len(g)} человеческих задания {T[rt]} заявки ({acts}) закрыты за {g.sec.min():.0f}–{g.sec.max():.0f} секунд после создания; обычно этапы занимают минуты–часы, ни одно другое задание в журнале не закрыто быстрее 188 с. Вероятно, массовое/формальное закрытие без реальной проверки.')
out=pd.DataFrame(rows,columns=['ProcessInstanceId','AnomalyType','Explanation']).drop_duplicates()
out.to_csv('/mnt/user-data/outputs/anomalies.csv',index=False,encoding='utf-8')
print(len(out), out.ProcessInstanceId.nunique()); print(out.AnomalyType.value_counts())
