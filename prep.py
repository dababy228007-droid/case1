import pandas as pd, numpy as np
df=pd.read_csv('/mnt/user-data/uploads/students.csv',encoding='utf-8-sig',dtype=str)
df['EventIndex']=df.EventIndex.astype(int); df['Amount']=df.Amount.astype(float)
df['ts']=pd.to_datetime(df.Timestamp,utc=True).dt.tz_convert('Etc/GMT-3')
df=df.sort_values(['ProcessInstanceId','EventIndex']).reset_index(drop=True)
short={'Проверка заявки':'CHK','Согласование руководителем':'MGR','Согласование бюджета':'BUD','Проверка договора':'LEG','Доработка заявки':'REW','Исполнение заявки':'EXE','Внеплановая проверка':'AUD'}
def route(g):
    out=[]
    for _,r in g.iterrows():
        if r.EventType=='task_completed': out.append(short[r.ActivityName]+':'+r.Result[0])
        elif r.EventType=='process_completed': out.append('END:'+r.Result[:3])
    return ' '.join(out)
routes=df.groupby('ProcessInstanceId').apply(route)
info=df.groupby('ProcessInstanceId').agg(rt=('RequestType','first'),amt=('Amount','first'),start=('ts','min'),end=('ts','max'),n=('EventId','count'))
info['route']=routes

# tasks table
cr=df[df.EventType=='task_created'][['ProcessInstanceId','TaskId','ActivityName','ts','EventIndex']].rename(columns={'ts':'t_cr','EventIndex':'i_cr'})
co=df[df.EventType=='task_completed'][['ProcessInstanceId','TaskId','ts','EventIndex','UserId','Role','Result']].rename(columns={'ts':'t_co','EventIndex':'i_co'})
tasks=cr.merge(co,on=['ProcessInstanceId','TaskId'],how='outer',indicator=True)
tasks['act']=tasks.ActivityName.map(short)
tasks['cal_h']=(tasks.t_co-tasks.t_cr).dt.total_seconds()/3600
def work_hours(a,b):
    if pd.isna(a) or pd.isna(b): return np.nan
    if b<=a: return 0.0
    tot=0.0; d=a.normalize()
    while d<=b:
        if d.weekday()<5:
            s=max(a,d+pd.Timedelta(hours=9)); e=min(b,d+pd.Timedelta(hours=18))
            if e>s: tot+=(e-s).total_seconds()/3600
        d+=pd.Timedelta(days=1)
    return tot
tasks['work_h']=[work_hours(a,b) for a,b in zip(tasks.t_cr,tasks.t_co)]
